from ultralytics import YOLO
import cv2
import numpy as np
import time
from kafka_config.kafka_config import KafkaMessenger
import json
from dotenv import load_dotenv
import os
import torch  # Import torch to check for CUDA availability

load_dotenv()

class StartTracker:
    def __init__(self, model_path):
        # Check if CUDA is available
        # self.device = 'cpu'
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[StartTracker] Using device: {self.device}")
        
        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.messenger_alertas = KafkaMessenger(topic='alertas')

        self.isSpecting = True
        self.detection_times = []  # Lista para armazenar os tempos de detecção
        self.required_time = 6  # Segundos necessários para interromper a inspeção
        self.statusPassoStart = False
        self.alertPassoStart = ''
        self.timeout_start = None  # Para o tempo limite de 60 segundos

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

    def process_video(self, frame):
        try:
            frame = cv2.resize(frame, (640, 640))
            
            # Move the frame to the same device as the model (if using CUDA)
            if self.device == 'cuda':
                frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0  # Normalize and move to GPU
                frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)  # Change shape to (1, 3, H, W)
            else:
                frame_tensor = frame  # Use the frame as-is for CPU


            # Perform inference
            results = self.model(frame_tensor, verbose=False)
            detected = False
            frame_width = frame.shape[1]
            right_region = 300  # Definir o lado direito (últimos 30% da largura do frame)

            for result in results:
                for box in result.boxes:
                    cls = result.names[int(box.cls)]  # Obter a classe detectada
                    x1, y1, x2, y2 = box.xyxy[0]  # Coordenadas do bounding box
                    
                    if x1 > right_region:
                        detected = True
                        break
                if detected:
                    break
            
            if detected:
                self.detection_times.append(time.time())
                if self.timeout_start is None:
                    self.timeout_start = time.time()  # Inicia o tempo limite
            else:
                # Se não houver detecção, verifica se o tempo limite foi excedido
                if self.timeout_start is not None and time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingStart']-1:
                    print("[Start Tracker] Tempo limite excedido para detecção do start.")
                    self.statusPassoStart = False
                    json_to_send = {"Posicionar na demarcação azul (área de chegada) de matéria prima": self.statusPassoStart}
                    self.alertPassoStart = 'Start não identificado'
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    self.timeout_start = None  # Reseta o tempo limite

                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)
            
            # Remover tempos antigos (> 20 segundos atrás)
            self.detection_times = [t for t in self.detection_times if time.time() - t <= self.required_time]
            
            # Verifica se a detecção foi contínua por 20 segundos
            if len(self.detection_times) > 0 and (self.detection_times[-1] - self.detection_times[0]) >= (self.required_time - 1):
                print("[Start Tracker] Start detectado. Encerrando inspeção.")
                self.statusPassoStart = True
                json_to_send = {"Posicionar na demarcação azul (área de chegada) de matéria prima": self.statusPassoStart}
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False
            
            # Desenha o frame processado
            frame = results[0].plot()
            # cv2.line(frame, (right_region, 0), (right_region, 640), (255, 255, 255), 2)

            return frame  # Retorna o frame processado
        except Exception as e:
            print(f'[StartTracker] Error processing frame: {e}')