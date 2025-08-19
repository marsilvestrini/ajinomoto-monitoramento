from ultralytics import YOLO
import cv2
import numpy as np
import time
from kafka_config.kafka_config import KafkaMessenger
import json
from dotenv import load_dotenv
import os
import torch
from datetime import datetime

load_dotenv()


class LabelPolpaTracker:
    def __init__(self, model_path):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[LabelPolpaTracker] Using device: {self.device}")

        # Carrega o modelo YOLO e move para o dispositivo correto
        self.model = YOLO(model_path).to(self.device)

        # Instancia os mensageiros Kafka
        self.messenger_passos = KafkaMessenger(topic="passos")
        self.messenger_alertas = KafkaMessenger(topic="alertas")

        # Carrega o JSON com configurações
        with open(os.getenv("JSON_PATH"), "r", encoding="utf-8") as arquivo:
            self.dados = json.load(arquivo)

        # Tempo necessário de detecção ou tempo máximo de espera
        self.required_time = self.dados["required_times"][0]["spectingLabelPolpa"] - 1
        self.timeout_max = self.dados["timeouts"][0]["spectingLabelPolpa"] - 1

        # ROI fixa (pode ser parametrizada depois)
        self.roi = (109, 409, 219, 639)  # (x1, y1, x2, y2)

        # Variáveis de controle da inspeção
        self.isSpecting = True
        self.statusPassoLabelPolpa = False
        self.alertPassoLabelPolpa = ""
        self.timeout_start = None
        self.detection_times = []

        # print("[LabelPolpaTracker] Inicialização completa.")

    def process_video(self, frame):
        try:
            if not self.isSpecting:
                return frame  # Se já concluiu ou falhou, não faz nada

            # Inicia o tempo de timeout na primeira chamada
            if self.timeout_start is None:
                self.timeout_start = time.time()

            # Redimensiona o frame para 640x640 (tamanho padrão dos outros trackers)
            frame = cv2.resize(frame, (640, 640))

            # Extrai a ROI definida
            x1, x2, y1, y2 = self.roi
            roi_frame = frame[y1:y2, x1:x2]

            # Executa a inferência apenas na ROI
            results = self.model(roi_frame, verbose=False)

            detected = False

            # Analisa os resultados
            for result in results:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    label = result.names[cls_id]
                    conf = float(box.conf[0])

                    if label == "etiqueta" and conf >= 0.6:
                        detected = True
                        # Converte coordenadas da ROI para o frame original
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        abs_x1, abs_y1 = bx1 + x1, by1 + y1
                        abs_x2, abs_y2 = bx2 + x1, by2 + y1

                        # Desenha o retângulo da detecção
                        cv2.rectangle(
                            frame, (abs_x1, abs_y1), (abs_x2, abs_y2), (0, 255, 0), 2
                        )
                        cv2.putText(
                            frame,
                            f"{label} {conf:.2f}",
                            (abs_x1, abs_y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 0),
                            1,
                        )

            # Se houve detecção, registra o timestamp
            if detected:
                self.detection_times.append(time.time())
            else:
                # Se passou do tempo sem detectar, envia alerta
                if time.time() - self.timeout_start > self.timeout_max:
                    print(
                        "[LabelPolpaTracker] Tempo limite excedido sem detectar etiqueta."
                    )
                    self.statusPassoLabelPolpa = False
                    self.alertPassoLabelPolpa = "Etiqueta não identificada na ROI"
                    self.isSpecting = False
                    self.messenger_passos.send_message(
                        {"Recolar a UC": self.statusPassoLabelPolpa}
                    )
                    self.messenger_alertas.send_message(
                        {
                            "alerta": True,
                            "type": "info",
                            "message": "Tempo limite excedido para detecção de etiquetas",
                        }
                    )

                    if os.getenv("SAVE_RESULTS"):
                        filename = os.path.join(
                            os.getenv("SAVE_PATH"), f"{datetime.now()}.jpg"
                        )
                        print(f"[Label Polpa Tracker] Saving file: {filename}")
                        cv2.imwrite(filename, frame)

                    return frame

            # Remove timestamps antigos (apenas últimos 'required_time' segundos contam)
            now = time.time()
            self.detection_times = [
                t for t in self.detection_times if now - t <= self.required_time
            ]

            # Se a detecção foi contínua o suficiente, finaliza com sucesso
            if len(self.detection_times) > 0 and (
                self.detection_times[-1] - self.detection_times[0]
            ) >= (self.required_time - 1):
                print("[LabelPolpaTracker] Etiqueta detectada com sucesso.")
                self.statusPassoLabelPolpa = True
                self.isSpecting = False
                self.messenger_passos.send_message(
                    {"Recolar a UC": self.statusPassoLabelPolpa}
                )

            # Desenha a ROI no frame
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(
                frame,
                "ROI Etiqueta",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                1,
            )

            return frame

        except Exception as e:
            print(f"[LabelPolpaTracker] Error processing frame: {e}")
            return frame
