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


class StartTracker:
    def __init__(self, model_path):
        # Check if CUDA is available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[StartTracker] Using device: {self.device}")

        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)

        self.messenger_passos = KafkaMessenger(topic="passos")
        self.messenger_alertas = KafkaMessenger(topic="alertas")

        self.isSpecting = True
        self.detection_times = []  # Lista para armazenar os tempos de detecção
        self.statusPassoStart = False
        self.alertPassoStart = ""
        self.timeout_start = None  # Para o tempo limite de 60 segundos

        with open(os.getenv("JSON_PATH"), "r", encoding="utf-8") as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = (
            self.dados["required_times"][0]["spectingStart"] - 1
        )  # Segundos necessários sem detecção para confirmar remoção

        # Definir a ROI (x, y, width, height)
        self.roi_x, self.roi_y, self.roi_width, self.roi_height = 375, 176, 205, 319

    def skip(self, skipJustification):
        print("[StartTracker] Etapa avançada via comando skip.")
        
        self.statusPassoStart = True 
        
        json_to_send = {
            "Posicionar na demarcação azul (área de chegada) de matéria prima": self.statusPassoStart,
            "skip": True,
            "justification": skipJustification
        }
        
        self.messenger_passos.send_message(json_to_send)
        
        self.isSpecting = False

    def process_video(self, frame):
        try:
            if self.timeout_start is None:
                self.timeout_start = time.time()

            frame = cv2.resize(frame, (640, 640))

            # Move the frame to the same device as the model (if using CUDA)
            # if self.device == 'cuda':
            #     frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0
            #     frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
            # else:
            frame_tensor = frame

            # Perform inference
            results = self.model(frame_tensor, verbose=False)
            detected = False

            # Definir os limites da ROI
            roi_x1, roi_y1 = self.roi_x, self.roi_y
            roi_x2, roi_y2 = roi_x1 + self.roi_width, roi_y1 + self.roi_height

            # Filtrar apenas as detecções dentro da ROI
            filtered_boxes = []
            filtered_cls = []
            filtered_scores = []

            for result in results:
                for box in result.boxes:
                    cls = int(box.cls)
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    label = self.model.names[cls]
                    conf = round(box.conf[0].item(), 2)
                    # Verificar se o bounding box está dentro da ROI
                    # if (x1 >= roi_x1 and y1 >= roi_y1 and
                    #     x2 <= roi_x2 and y2 <= roi_y2 and label == 'pallet' and conf >= 0.65):
                    if (
                        x1 >= roi_x1
                        and y1 >= roi_y1
                        and x2 <= roi_x2
                        and y2 <= roi_y2
                        and not "pessoa" in label
                    ):
                        detected = True
                        filtered_boxes.append([x1, y1, x2, y2])
                        filtered_cls.append(cls)
                        filtered_scores.append(float(box.conf))

            # Atualizar o status de detecção
            if detected:
                self.detection_times.append(time.time())

            else:
                # Se não houver detecção, verifica se o tempo limite foi excedido
                if (
                    self.timeout_start is not None
                    and time.time() - self.timeout_start
                    > self.dados["timeouts"][0]["spectingStart"] - 1
                ):
                    print(
                        "[Start Tracker] Tempo limite excedido para detecção do start."
                    )
                    self.statusPassoStart = False
                    json_to_send = {
                        "Posicionar na demarcação azul (área de chegada) de matéria prima": self.statusPassoStart
                    }
                    self.alertPassoStart = "Start não identificado"
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    self.timeout_start = None

                    json_alert = {
                        "alerta": True,
                        "type": "info",
                        "message": "Tempo limite excedido para o inicio da detecção",
                    }
                    self.messenger_alertas.send_message(json_alert)

                    if os.getenv("SAVE_RESULTS"):
                        filename = os.path.join(
                            os.getenv("SAVE_PATH"), f"{datetime.now()}.jpg"
                        )
                        print(f"[Start Tracker] Saving file: {filename}")
                        cv2.imwrite(filename, frame)

            # Remover tempos antigos (> required_time segundos atrás)
            self.detection_times = [
                t for t in self.detection_times if time.time() - t <= self.required_time
            ]

            # Verifica se a detecção foi contínua por required_time segundos
            if len(self.detection_times) > 0 and (
                self.detection_times[-1] - self.detection_times[0]
            ) >= (self.required_time - 1):
                print("[Start Tracker] Start detectado. Encerrando inspeção.")
                self.statusPassoStart = True
                json_to_send = {
                    "Posicionar na demarcação azul (área de chegada) de matéria prima": self.statusPassoStart
                }
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False

            # Criar uma cópia do frame original para desenhar
            output_frame = frame.copy()

            # Desenhar apenas as detecções dentro da ROI
            for box, cls, score in zip(filtered_boxes, filtered_cls, filtered_scores):
                x1, y1, x2, y2 = map(int, box)
                color = (0, 255, 0)  # Verde para detecções dentro da ROI
                cv2.rectangle(output_frame, (x1, y1), (x2, y2), color, 2)

                # Adicionar label e confiança
                label = f"{results[0].names[cls]}: {score:.2f}"
                cv2.putText(
                    output_frame,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

            # Desenhar a ROI para referência (vermelho)
            cv2.rectangle(
                output_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 0, 255), 2
            )
            cv2.putText(
                output_frame,
                "ROI Carga",
                (roi_x1, roi_y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                2,
            )

            return output_frame
        except Exception as e:
            print(f"[StartTracker] Error processing frame: {e}")
            return frame

