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

class StretchTracker:
    def __init__(self, model_path):
        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[StretchTracker] Using device: {self.device}")
        
        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.messenger_alertas = KafkaMessenger(topic='alertas')

        self.isSpecting = True
        self.detection_times = []  # Lista para armazenar os tempos de detecção
        self.statusPassoStretch = False
        self.alertPassoStretch = ''
        self.timeout_start = None  # Para o tempo limite de 60 segundos
        self.confidence = None

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = self.dados['required_times'][0]['spectingStrech']-1  # Segundos necessários para interromper a inspeção
        

    def process_video(self, frame):
        try:
            if frame is None:
                print("[StretchTracker] Received empty frame")
                return None

            if self.timeout_start is None:
                self.timeout_start = time.time()
                
            # Resize and convert frame
            # frame = cv2.resize(frame, (640, 640))
            # frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convert to RGB
            
            # Perform inference
            results = self.model(frame, verbose=False)  # Let YOLO handle the device conversion
            
            detected = False
            frame_width = frame.shape[1]
            right_region = 300  # Right side region (last 30% of frame width)
            self.confidence = 0  # Reset confidence

            for result in results:
                for box in result.boxes:
                    cls = int(box.cls)  # Get class index
                    label = self.model.names[cls]  # Get class label
                    self.confidence = box.conf[0].item()  # Get confidence
                    
                    # print(f"Detected: {label} with confidence: {self.confidence:.2f}")
                    
                    if label == 'strechadeira' and self.confidence >= 0.6:
                        detected = True
                        # Only draw 'strechadeira' detections
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, 
                                f"{label} {self.confidence:.2f}", 
                                (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.6, (0, 255, 0), 2)
                if detected:
                    break
            
            if detected:
                self.detection_times.append(time.time())
            else:
                # Check timeout if no detection
                if (self.timeout_start is not None and 
                    time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingStrech']-1):
                    print("[Stretch Tracker] Timeout exceeded for stretch detection.")
                    self.statusPassoStretch = False
                    json_to_send = {"PassoStretch": self.statusPassoStretch}
                    self.alertPassoStretch = 'Strechar o palete de plástico"'
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    self.timeout_start = None

                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)
            
            # Remove old detection times (> required_time seconds ago)
            current_time = time.time()
            self.detection_times = [t for t in self.detection_times if current_time - t <= self.required_time]
            
            # Check for continuous detection
            if (len(self.detection_times) > 0 and 
                (self.detection_times[-1] - self.detection_times[0]) >= (self.required_time - 1)):
                print("[Stretch Tracker] Stretch detected. Ending inspection.")
                self.statusPassoStretch = True
                json_to_send = {"Strechar o palete de plástico": self.statusPassoStretch}
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False
            
            
            # Return the original frame with just the line if no detection
            cv2.line(frame, (right_region, 0), (right_region, 640), (255, 255, 255), 2)
            return frame
                
        except Exception as e:
            print(f'[StretchTracker] Error processing frame: {str(e)}')
            # Return the original frame if processing fails
            if frame is not None:
                cv2.line(frame, (right_region, 0), (right_region, 640), (255, 255, 255), 2)
                return frame
            return None