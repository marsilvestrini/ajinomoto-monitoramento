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

        self.isTracking = False
        self.detection_times = []  # Lista para armazenar os tempos de não detecção
        self.required_time = 6  # Segundos necessários sem detecção para confirmar remoção
        self.statusPassoFinish = False
        self.alertPassoFinish = ''
        self.timeout_start = None  # Para o tempo limite de 60 segundos
        self.last_detection_time = None  # Tempo da última detecção
        self.initial_detection_made = False  # Flag para verificar primeira detecção

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

    def process_video(self, frame):
        try:
            frame = cv2.resize(frame, (640, 640))
            
            # Move the frame to the same device as the model (if using CUDA)
            if self.device == 'cuda':
                frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0
                frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
            else:
                frame_tensor = frame

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
                self.last_detection_time = time.time()
                self.initial_detection_made = True  # Marca que o objeto foi detectado pelo menos uma vez
                self.detection_times = []  # Reseta os tempos de não detecção
                
                if self.timeout_start is None:
                    self.timeout_start = time.time()  # Inicia o tempo limite
            else:
                if self.initial_detection_made:  # Só começa a contar se já houve uma detecção antes
                    self.detection_times.append(time.time())
                
                # Verifica tempo limite se ainda não houve detecção inicial
                if not self.initial_detection_made and self.timeout_start is not None and time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingFinish']-1:
                    print("[Finish Tracker] Tempo limite excedido para detecção inicial do objeto.")
                    self.statusPassoFinish = False
                    json_to_send = {"Remover da demarcação azul (área de chegada) de matéria prima": self.statusPassoFinish}
                    self.alertPassoFinish = 'Objeto não foi detectado inicialmente'
                    self.messenger_passos.send_message(json_to_send)
                    self.isTracking = False
                    self.timeout_start = None
                    
                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)
            
            # Remover tempos antigos (> required_time segundos atrás)
            self.detection_times = [t for t in self.detection_times if time.time() - t <= self.required_time]
            
            # Verifica se o objeto ficou ausente por required_time segundos após detecção inicial
            if (self.initial_detection_made and len(self.detection_times) > 0 and 
                (self.detection_times[-1] - self.detection_times[0]) >= (self.required_time - 1)):
                print("[Finish Tracker] Objeto removido da área de chegada. Processo concluído.")
                self.statusPassoFinish = True
                json_to_send = {"Remover da demarcação azul (área de chegada) de matéria prima": self.statusPassoFinish}
                self.messenger_passos.send_message(json_to_send)
                self.isTracking = False
                self.initial_detection_made = False  # Reseta para próxima verificação
            
            # Desenha o frame processado
            frame = results[0].plot()
            
            return frame
        except Exception as e:
            print(f'[FinishTracker] Error processing frame: {e}')