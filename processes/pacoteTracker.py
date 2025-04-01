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
        self.roi_vertices = np.array([(249, 341), (573, 341), (573, 611), (249, 611)], np.int32)
        self.produtos = ["balde", "caixa", "galao", "pacote"]
        self.isSpecting = True
        self.last_detection_time = None
        self.start_time = None
        self.pacotes_contados = 0
        self.last_count_time = time.time()  # Tempo da última contagem
        self.roi = (393, 202, 126, 200)  # ROI: (x, y, width, height)
        self.y_line_position = 360
        self.statusPassoProduto = False
        self.alertPassoProduto = ''

        self.messenger_alertas = KafkaMessenger(topic='alertas')

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = self.dados['required_times'][0]['spectingPacotes']-1  # Segundos necessários para interromper a inspeção
        

    def is_inside_roi(self, box):
        x1, y1, x2, y2 = box
        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
        roi_x, roi_y, roi_w, roi_h = self.roi
        return (roi_x <= center_x <= roi_x + roi_w) and (roi_y <= center_y <= roi_y + roi_h)

    def get_center(self, box):
        x1, y1, x2, y2 = box
        return (x1 + x2) // 2, (y1 + y2) // 2

    def track_transition(self, current_centers):
        # Lista para armazenar os índices dos pacotes que já foram contados
        pacotes_ja_contados = []

        # Ordenar os centroides pelo valor de x (menor x primeiro)
        self.prev_centers.sort(key=lambda center: center[0])
        current_centers.sort(key=lambda center: center[0])

        if len(self.prev_centers) == len(current_centers):
            # Garantir que as listas tenham o mesmo tamanho
            min_length = min(len(self.prev_centers), len(current_centers))
            for i in range(min_length):
                prev_center_x, prev_center_y = self.prev_centers[i]
                curr_center_x, curr_center_y = current_centers[i]

                if prev_center_x > self.y_line_position and curr_center_x < self.y_line_position:

                    # Verificar se o pacote já foi contado
                    if i not in pacotes_ja_contados:
                        # Verificar se já passou tempo suficiente desde a última contagem
                        if time.time() - self.last_count_time > 1:  # Intervalo de 1 segundo
                            self.pacotes_contados += 1
                            self.last_count_time = time.time()
                            pacotes_ja_contados.append(i)  # Marcar o pacote como contado
                            # print("Pacote passou para o lado direito.")
                            # print("Pacotes contados:", self.pacotes_contados)

    def check_etiqueta_inside_pacote(self, pacote_box, etiqueta_boxes):
        x1_p, y1_p, x2_p, y2_p = pacote_box
        for x1_e, y1_e, x2_e, y2_e in etiqueta_boxes:
            if x1_e >= x1_p and y1_e >= y1_p and x2_e <= x2_p and y2_e <= y2_p:
                return True
        return False

    def check_roi_detections(self, produto_boxes):
        for pacote_box in produto_boxes:
            if self.is_inside_roi(pacote_box):
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
                self.alertPassoProduto = "Timeover excedido para descarregamento de produtos."
                print("[Produto Tracker] Timeover excedido para descarregamento de produtos.") 

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
            etiqueta_boxes = []
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = box.conf[0].item()
                    cls = int(box.cls[0].item())
                    label = self.model.names[cls]

                    if label in self.produtos:
                        produto_boxes.append((x1, y1, x2, y2))
                    elif label == "etiqueta":
                        etiqueta_boxes.append((x1, y1, x2, y2))
        
            current_centers = [self.get_center(box) for box in produto_boxes]

            self.track_transition(current_centers)

            self.prev_centers = current_centers

            roi_detections = self.check_roi_detections(produto_boxes)

            if roi_detections:
                self.last_detection_time = time.time()
            else:
                if time.time() - self.last_detection_time > self.required_time:
                    self.statusPassoProduto = True
                    json_to_send = {"Descarregar os produtos": self.statusPassoProduto}
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    print(f"[Produto Tracker] Nenhuma detecção no ROI por {self.required_time} segundos. Parando a inspeção.")

            for idx, box in enumerate(produto_boxes):
                    x1, y1, x2, y2 = box
                    if x1 < self.y_line_position:
                        color = (0, 255, 0) if self.check_etiqueta_inside_pacote(box, etiqueta_boxes) else (0, 0, 255)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(frame, f"{x1,y1}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            for etiqueta_box in etiqueta_boxes:
                x1, y1, x2, y2 = etiqueta_box
                if x1 < self.y_line_position:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

            # Desenha o ROI no frame
            roi_x, roi_y, roi_w, roi_h = self.roi
            cv2.rectangle(frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (0, 255, 255), 2)  # Amarelo
            cv2.line(frame, (self.y_line_position, 0), (self.y_line_position, 640), (255, 255, 255), 2)
            # cv2.putText(frame, f"Pacotes contados: {self.pacotes_contados}", (15, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # print("Pacotes sem etiqueta:", self.pacotes_sem_etiqueta)

            return frame  # Retorna o frame processado
        except Exception as e:
            print(f"[PacoteTracker] Error processing frame: {e}")