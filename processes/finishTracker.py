from ultralytics import YOLO
import cv2
import numpy as np
import time
from kafka_config.kafka_config import KafkaMessenger
import json
from dotenv import load_dotenv
import os
import torch

load_dotenv()

class FinishTracker:
    def __init__(self, model_path):
        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[FinishTracker] Using device: {self.device}")
        
        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.messenger_alertas = KafkaMessenger(topic='alertas')

        self.isSpecting = True
        self.detection_times = []  # Lista para armazenar os tempos de não detecção
        self.statusPassoFinish = False
        self.alertPassoFinish = ''
        self.timeout_start = None  # Para o tempo limite de 60 segundos
        self.last_detection_time = None  # Tempo da última detecção
        self.initial_detection_made = False  # Flag para verificar primeira detecção

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = self.dados['required_times'][0]['spectingFinish']-1  # Segundos necessários sem detecção para confirmar remoção
        
        # Definir a ROI (x, y, width, height)
        self.roi_x, self.roi_y, self.roi_width, self.roi_height = 177, 176, 201, 319

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

                    # Verificar se o bounding box está dentro da ROI
                    # if (x1 >= roi_x1 and y1 >= roi_y1 and 
                    #     x2 <= roi_x2 and y2 <= roi_y2 and label == 'pallet'):
                    if (x1 >= roi_x1 and y1 >= roi_y1 and 
                        x2 <= roi_x2 and y2 <= roi_y2):
                        detected = True
                        filtered_boxes.append([x1, y1, x2, y2])
                        filtered_cls.append(cls)
                        filtered_scores.append(float(box.conf))
            
            # Atualizar o status de detecção
            if detected:
                self.last_detection_time = time.time()
                self.initial_detection_made = True
                self.detection_times = []
                
            else:
                if self.initial_detection_made:
                    self.detection_times.append(time.time())
                
                if (not self.initial_detection_made and 
                    self.timeout_start is not None and 
                    time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingFinish']-1):
                    print("[Finish Tracker] Tempo limite excedido para detecção inicial do objeto.")
                    self.statusPassoFinish = False
                    json_to_send = {"Transferir o palete para fora da área de manipulação": self.statusPassoFinish}
                    self.alertPassoFinish = 'Objeto não foi detectado inicialmente'
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    self.timeout_start = None
                    
                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)
            
            # Remover tempos antigos (> required_time segundos atrás)
            self.detection_times = [t for t in self.detection_times if time.time() - t <= self.required_time]
            
            # Verificar se o objeto ficou ausente por required_time segundos
            if (self.initial_detection_made and len(self.detection_times) > 0 and 
                (self.detection_times[-1] - self.detection_times[0]) >= (self.required_time - 1)):
                print("[Finish Tracker] Objeto removido da área de manipulação. Processo concluído.")
                self.statusPassoFinish = True
                json_to_send = {"Transferir o palete para fora da área de manipulação": self.statusPassoFinish}
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False
                self.initial_detection_made = False
            
            # Desenhar apenas as detecções dentro da ROI
            for box, cls, score in zip(filtered_boxes, filtered_cls, filtered_scores):
                x1, y1, x2, y2 = map(int, box)
                color = (0, 255, 0)  # Verde para detecções dentro da ROI
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Adicionar label e confiança
                label = f"{results[0].names[cls]}: {score:.2f}"
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Desenhar a ROI para referência
            cv2.rectangle(frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 0, 255), 2)
            cv2.putText(frame, "ROI Descarga", (roi_x1, roi_y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            # cv2.putText(frame, "ROI fi", (roi_x1, roi_y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            return frame
        except Exception as e:
            print(f'[FinishTracker] Error processing frame: {e}')
            return frame