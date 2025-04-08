from ultralytics import YOLO
import cv2
import numpy as np
import time
from kafka_config.kafka_config import KafkaMessenger
import torch  # Import torch to check for CUDA availability
from dotenv import load_dotenv
import os
import json

load_dotenv()
class PacoteTracker:
    def __init__(self, model_path):
        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[PacoteTracker] Using device: {self.device}")
        
        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.prev_centers = []  # Lista para armazenar os centroides anteriores
        self.pacotes_sem_etiqueta = []  # Lista para armazenar pacotes sem etiqueta
        self.produtos = ["balde", "caixa", "galao", "pacote"]
        self.isSpecting = True
        self.last_detection_time = None
        self.start_time = None
        self.pacotes_contados = 0
        self.last_count_time = time.time()  # Tempo da última contagem
        self.roi_carga = (375, 176, 205, 319)  # ROI de carga: (x, y, width, height)
        self.roi_descarga = (177, 177, 201, 313)  # ROI de descarga: (x, y, width, height)
        self.y_line_position = 360
        self.statusPassoProduto = False
        self.alertPassoProduto = ''
        self.min_confidence = 0.55  # Limite mínimo de confiança para produtos na área de descarga

        self.messenger_alertas = KafkaMessenger(topic='alertas')

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = self.dados['required_times'][0]['spectingPacotes']-1  # Segundos necessários para interromper a inspeção
        

    def is_inside_roi(self, box, roi):
        x1, y1, x2, y2 = box
        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
        roi_x, roi_y, roi_w, roi_h = roi
        return (roi_x <= center_x <= roi_x + roi_w) and (roi_y <= center_y <= roi_y + roi_h)

    def get_center(self, box):
        x1, y1, x2, y2 = box
        return (x1 + x2) // 2, (y1 + y2) // 2

    def check_etiqueta_inside_pacote(self, pacote_box, etiqueta_boxes):
        x1_p, y1_p, x2_p, y2_p = pacote_box
        for x1_e, y1_e, x2_e, y2_e in etiqueta_boxes:
            if x1_e >= x1_p and y1_e >= y1_p and x2_e <= x2_p and y2_e <= y2_p:
                return True
        return False

    def check_roi_detections(self, produto_boxes, produto_confs, roi, min_confidence=0):
        for i, pacote_box in enumerate(produto_boxes):
            if self.is_inside_roi(pacote_box, roi) and produto_confs[i] >= min_confidence:
                return True
        return False

    def process_video(self, frame):
        try:
            # Resize the frame
            if not self.last_detection_time:
                self.last_detection_time = time.time()
                self.start_time = time.time()

            if time.time() - self.start_time > self.dados['timeouts'][0]['spectingPacotes']-1:
                self.statusPassoProduto = False
                json_to_send = {"Descarregar os produtos": self.statusPassoProduto}
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False
                self.alertPassoProduto = "Timeout excedido para descarregamento de produtos."
                print("[Produto Tracker] Timeout excedido para descarregamento de produtos.") 

                json_alert = {"alerta": True}
                self.messenger_alertas.send_message(json_alert)               

            frame = cv2.resize(frame, (640, 640))
            
            # Move the frame to the same device as the model (if using CUDA)
            if self.device == 'cuda':
                frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0  # Normalize and move to GPU
                frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)  # Change shape to (1, 3, H, W)
            else:
                frame_tensor = frame  # Use the frame as-is for CPU

            # Perform inference
            results = self.model(frame_tensor, verbose=False)
            
            produto_boxes = []
            produto_confs = []  # Armazena as confianças dos produtos
            produto_labels = []  # Armazena os labels dos produtos
            etiqueta_boxes = []
            etiqueta_confs = []  # Armazena as confianças das etiquetas
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = round(box.conf[0].item(), 2)  # Arredonda para 2 casas decimais
                    cls = int(box.cls[0].item())
                    label = self.model.names[cls]

                    if label in self.produtos:
                        produto_boxes.append((x1, y1, x2, y2))
                        produto_confs.append(conf)
                        produto_labels.append(label)
                    elif label == "etiqueta":
                        etiqueta_boxes.append((x1, y1, x2, y2))
                        etiqueta_confs.append(conf)

            # Verifica detecções em ambos os ROIs (com filtro de confiança para descarga)
            roi_carga_detections = self.check_roi_detections(produto_boxes, produto_confs, self.roi_carga)
            roi_descarga_detections = self.check_roi_detections(produto_boxes, produto_confs, self.roi_descarga, self.min_confidence)

            if roi_carga_detections or roi_descarga_detections:
                self.last_detection_time = time.time()
            else:
                if time.time() - self.last_detection_time > self.required_time:
                    self.statusPassoProduto = True
                    json_to_send = {"Descarregar os produtos": self.statusPassoProduto}
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    print(f"[Produto Tracker] Nenhuma detecção nos ROIs por {self.required_time} segundos. Parando a inspeção.")

            for idx, box in enumerate(produto_boxes):
                x1, y1, x2, y2 = box
                conf = produto_confs[idx]
                label = produto_labels[idx]
                
                # Verifica em qual ROI o pacote está
                in_carga = self.is_inside_roi(box, self.roi_carga)
                in_descarga = self.is_inside_roi(box, self.roi_descarga) and conf >= self.min_confidence
                
                if in_carga:
                    # ROI de Carga - mostra confiança (azul)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    cv2.putText(frame, f"{label} {conf}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                elif in_descarga:
                    # ROI de Descarga - verifica etiqueta e mostra confiança (verde/vermelho)
                    has_etiqueta = self.check_etiqueta_inside_pacote(box, etiqueta_boxes)
                    color = (0, 255, 0) if has_etiqueta else (0, 0, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    status = "COM ETIQUETA" if has_etiqueta else "SEM ETIQUETA"
                    cv2.putText(frame, f"{label} {status} {conf}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            for idx, etiqueta_box in enumerate(etiqueta_boxes):
                x1, y1, x2, y2 = etiqueta_box
                conf = etiqueta_confs[idx]  # Obtém a confiança correspondente
                in_descarga = self.is_inside_roi(etiqueta_box, self.roi_descarga)
                if in_descarga:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)  # Amarelo para etiquetas
                    cv2.putText(frame, f"Etiqueta {conf}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # Desenha os ROIs no frame
            # ROI de Carga (vermelho)
            roi_x, roi_y, roi_w, roi_h = self.roi_carga
            cv2.rectangle(frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 0, 255), 2)
            cv2.putText(frame, "ROI Carga", (roi_x, roi_y-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # ROI de Descarga (verde)
            roi_x, roi_y, roi_w, roi_h = self.roi_descarga
            cv2.rectangle(frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 255, 0), 2)
            cv2.putText(frame, "ROI Descarga", (roi_x, roi_y-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            return frame  # Retorna o frame processado
        except Exception as e:
            print(f"[PacoteTracker] Error processing frame: {e}")