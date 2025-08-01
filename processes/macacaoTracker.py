from ultralytics import YOLO
import cv2
import numpy as np
import time
from kafka_config.kafka_config import KafkaMessenger
import json
from dotenv import load_dotenv
import os
import torch  # Import torch to check for CUDA availability
from datetime import datetime

load_dotenv()

class MacacaoTracker:
    def __init__(self, model_path, expected_macacao_color):
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.messenger_alertas = KafkaMessenger(topic='alertas')

        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        #print(f"[MacacaoTracker] Using device: {self.device}")
        # self.device ='cpu'
        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.isSpecting = True
        self.detection_times = []  # Lista para armazenar os tempos de detecção
        self.statusPassoMacacao = False
        self.alertPassoMacacao = ''
        self.timeout_start = None  # Para o tempo limite de 60 segundos
        self.expected_macacao_color = expected_macacao_color

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = self.dados['required_times'][0]['spectingMacacao']-1  # Segundos necessários sem detecção para confirmar remoção
          

    def process_video(self, frame):
        try:
            if self.timeout_start is None:
                self.timeout_start = time.time()  # Inicia o tempo limite

            frame = cv2.resize(frame, (640, 640))

            if self.expected_macacao_color == "macacao_branco":
                print(f'[Macacao Tracker] Classe esperada: {self.expected_macacao_color}, pulando etapa.')
                self.isSpecting = False
                return frame
            
            # Move the frame to the same device as the model (if using CUDA)
            # if self.device == 'cuda':
            #     frame = torch.from_numpy(frame).to(self.device).float() / 255.0  # Normalize and move to GPU
            #     frame = frame.permute(2, 0, 1).unsqueeze(0)  # Change shape to (1, 3, H, W)
            
            results = self.model(frame, verbose=False)
            detected = False
            frame_width = frame.shape[1]
            right_region = 300  # Definir o lado direito (últimos 30% da largura do frame)

            for result in results:
                for box in result.boxes:
                    cls = result.names[int(box.cls)]  # Obter a classe detectada
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cls = int(box.cls[0].item())
                    label = self.model.names[cls]
                    conf = round(box.conf[0].item(), 2)
                    if label == self.expected_macacao_color and conf >= 0.75:
                        detected = True
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, 
                                f"{label} {conf:.2f}", 
                                (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.6, (0, 255, 0), 2)
                        break
                if detected:
                    break
            
            if detected:
                self.detection_times.append(time.time())
            else:
                # Se não houver detecção, verifica se o tempo limite foi excedido
                if self.timeout_start is not None and time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingMacacao']-1:
                    print("[Macacao Tracker] Tempo limite excedido para detecção de macacao.")
                    self.statusPassoMacacao = False
                    json_to_send = {"Colocar o macacão azul para manusear o material": self.statusPassoMacacao}
                    self.alertPassoMacacao = 'Macacão azul não identificado'
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    self.timeout_start = None  # Reseta o tempo limite

                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)

                    if os.getenv('SAVE_RESULTS'):
                        filename = os.path.join(os.getenv('SAVE_PATH'),f"{datetime.now()}.jpg")
                        print(f"[Macacao Tracker] Saving file: {filename}")
                        cv2.imwrite(filename, frame)
            
            # Remover tempos antigos (> x segundos atrás)
            self.detection_times = [t for t in self.detection_times if time.time() - t <= self.required_time]
            
            # Verifica se a detecção foi contínua por x segundos
            if len(self.detection_times) > 0 and (self.detection_times[-1] - self.detection_times[0]) >= (self.required_time - 1):
                print("[Macacao Tracker] Macacao detectado. Encerrando inspeção.")
                self.statusPassoMacacao = True
                json_to_send = {"Colocar o macacão azul para manusear o material": self.statusPassoMacacao}
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False
            
            return frame  # Retorna o frame processado
        except Exception as e:
            print(f"[MacacaoTracker] Error processing frame: {e}")