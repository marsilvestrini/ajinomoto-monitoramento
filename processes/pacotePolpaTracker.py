from ultralytics import YOLO
import cv2
import time
from kafka_config.kafka_config import KafkaMessenger
import torch
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv()


class PacotePolpaTracker:
    def __init__(self, model_path):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[PacotePolpaTracker] Using device: {self.device}")

        self.model = YOLO(model_path).to(self.device)
        self.messenger_passos = KafkaMessenger(topic="passos")
        self.messenger_alertas = KafkaMessenger(topic="alertas")

        # Produtos a serem detectados
        self.produtos = ["balde", "caixa", "galao", "pacote"]
        self.min_confidence = 0.55

        # ROIs
        self.roi_carga = (375, 176, 205, 319)
        self.roi_descarga = (177, 176, 201, 319)

        # pg
        self.statusPassoPacotePolpa = False
        self.alertsPassoPacotePolpa = ""

        # Estados do procedimento
        self.estagios = {
            0: "waiting_descarga_1",
            1: "waiting_remocao_1",
            2: "waiting_descarga_2",
            3: "waiting_remocao_2",
        }
        self.estagio_atual = 0
        self.estagio_timer = None
        self.isSpecting = True

        # timestampas de controle
        self.start_time = None
        self.last_detection_time = None

        # Carregar configurações
        with open(os.getenv("JSON_PATH"), "r", encoding="utf-8") as arquivo:
            self.dados = json.load(arquivo)

        # Tempos mínimos para cada estado
        self.tempo_presenca = self.dados["required_times"][0]["presença_polpa"]
        self.tempo_ausencia = self.dados["required_times"][0]["ausencia_polpa"]
        self.timeout_geral = self.dados["timeouts"][0]["spectingPacotes"]

        print(
            f"[PacotePolpaTracker] Configuração carregada: Tempo presença={self.tempo_presenca}s, Tempo ausência={self.tempo_ausencia}s"
        )

    def skip(self):
        print("[PacotePolpaTracker] Etapa avançada via comando skip.")
        
        self.statusPassoPacotePolpa = True 
        
        json_to_send = {
            "Descarregar os produtos": self.statusPassoPacotePolpa,
            "skip": True  
        }
        
        self.messenger_passos.send_message(json_to_send)
        
        self.isSpecting = False

    def is_inside_roi(self, box, roi):
        x1, y1, x2, y2 = box
        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
        roi_x, roi_y, roi_w, roi_h = roi
        return (roi_x <= center_x <= roi_x + roi_w) and (
            roi_y <= center_y <= roi_y + roi_h
        )

    def has_detections_in_carga(self, produto_boxes, produto_confs):
        for i, box in enumerate(produto_boxes):
            if produto_confs[i] >= self.min_confidence and self.is_inside_roi(
                box, self.roi_carga
            ):
                return True
        return False

    def avancar_estagio(self, novo_estagio):
        self.estagio_atual = novo_estagio
        self.estagio_timer = time.time()
        print(f"[EstágioPolpa] Transição para {self.estagios[novo_estagio]}")

    def enviar_conclusao_kafka(self, status):
        status_msg = {"Descarregar os produtos": status}
        self.messenger_passos.send_message(status_msg)
        print("[Kafka] Mensagem final enviada: PacotePolpa concluído")

    def process_video(self, frame):
        try:
            if not self.start_time or self.last_detection_time:
                self.start_time = time.time()
                self.last_detection_time = time.time()
            # Verificar timeout geral
            if time.time() - self.start_time > self.timeout_geral:
                self.isSpecting = False
                self.statusPassoPacotePolpa = False
                alerta = {
                    "alerta": True,
                    "type": "info",
                    "message": "Tempo limite excedido no procedimento de descarga",
                }
                self.messenger_alertas.send_message(alerta)
                print("[PacotePolpaTracker] Timeout excedido")
                self.enviar_conclusao_kafka(self.statusPassoPacotePolpa)

                if os.getenv("SAVE_RESULTS"):
                    filename = os.path.join(
                        os.getenv("SAVE_PATH"), f"{datetime.now()}.jpg"
                    )
                    print(f"[PacotePolpaTracker] Saving file: {filename}")
                    cv2.imwrite(filename, frame)

                return frame

            # Pré-processamento
            frame = cv2.resize(frame, (640, 640))
            results = self.model(frame, verbose=False)

            # Detecção de produtos
            produto_boxes = []
            produto_confs = []

            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = round(box.conf[0].item(), 2)
                    cls = int(box.cls[0].item())
                    label = self.model.names[cls]

                    if label in self.produtos and conf >= self.min_confidence:
                        produto_boxes.append((x1, y1, x2, y2))
                        produto_confs.append(conf)

            # Verificar ROI de descarga
            tem_detec_descarga = self.has_detections_in_carga(
                produto_boxes, produto_confs
            )

            # Máquina de estados do procedimento
            if self.estagio_atual == 0:  # Aguardando primeira descarga
                if tem_detec_descarga:
                    if self.estagio_timer is None:
                        self.estagio_timer = time.time()
                    elif time.time() - self.estagio_timer >= self.tempo_presenca:
                        self.avancar_estagio(1)
                else:
                    self.estagio_timer = None

            elif self.estagio_atual == 1:  # Aguardando remoção primeira
                if not tem_detec_descarga:
                    if self.estagio_timer is None:
                        self.estagio_timer = time.time()
                    elif time.time() - self.estagio_timer >= self.tempo_ausencia:
                        self.avancar_estagio(2)
                else:
                    self.estagio_timer = None

            elif self.estagio_atual == 2:  # Aguardando segunda descarga
                if tem_detec_descarga:
                    if self.estagio_timer is None:
                        self.estagio_timer = time.time()
                    elif time.time() - self.estagio_timer >= self.tempo_presenca:
                        self.avancar_estagio(3)
                else:
                    self.estagio_timer = None

            elif self.estagio_atual == 3:  # Aguardando remoção segunda
                if not tem_detec_descarga:
                    if self.estagio_timer is None:
                        self.estagio_timer = time.time()
                    elif time.time() - self.estagio_timer >= self.tempo_ausencia:
                        self.isSpecting = False
                        self.statusPassoPacotePolpa = True
                        self.enviar_conclusao_kafka(self.statusPassoPacotePolpa)
                        print(
                            "[PacotePolpaTracker] Procedimento concluído com sucesso!"
                        )
                else:
                    self.estagio_timer = None

            # Desenhar ROIs e informações
            roi_x, roi_y, roi_w, roi_h = self.roi_carga
            cv2.rectangle(
                frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 0, 255), 2
            )
            cv2.putText(
                frame,
                "ROI Carga",
                (roi_x, roi_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                2,
            )

            roi_x, roi_y, roi_w, roi_h = self.roi_descarga
            cv2.rectangle(
                frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 255, 0), 2
            )
            cv2.putText(
                frame,
                "ROI Descarga",
                (roi_x, roi_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

            # Mostrar estágio atual
            cv2.putText(
                frame,
                f"Estagio: {self.estagios[self.estagio_atual]}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 255),
                1,
            )

            # # Mostrar contador de timeout
            # tempo_restante = max(0, self.timeout_geral - (time.time() - self.start_time))
            # cv2.putText(frame, f"Timeout: {tempo_restante:.1f}s", (10, 60),
            #           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

            return frame

        except Exception as e:
            print(f"[PacotePolpaTracker] Erro: {e}")
            self.messenger_alertas.send_message(
                {
                    "alerta": True,
                    "type": "error",
                    "message": f"Erro no processamento: {str(e)}",
                }
            )
            return frame

