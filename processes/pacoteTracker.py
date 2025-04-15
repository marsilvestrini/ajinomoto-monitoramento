from ultralytics import YOLO
import cv2
import numpy as np
import time
from kafka_config.kafka_config import KafkaMessenger
import torch
from dotenv import load_dotenv
import os
import json

load_dotenv()

class PacoteTracker:
    def __init__(self, model_path, procedure_name):
        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[PacoteTracker] Using device: {self.device}")
        
        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.prev_centers = []
        self.pacotes_sem_etiqueta = []
        self.produtos = ["balde", "caixa", "galao", "pacote"]
        self.isSpecting = True
        self.last_detection_time = None
        self.start_time = None
        self.pacotes_contados = 0
        self.last_count_time = time.time()
        self.roi_carga = (375, 176, 205, 319)
        self.roi_descarga = (177, 176, 201, 319)
        self.y_line_position = 360
        self.statusPassoProduto = False
        self.alertPassoProduto = ''
        self.min_confidence = 0.55

        # Configurações para rastreamento de etiquetas
        self.pacote_states = {}  # {id: {'first_seen': timestamp, 'last_seen': timestamp, 'has_etiqueta': bool, 
                               # 'color': tuple, 'last_center': tuple, 'last_etiqueta_time': timestamp, 
                               # 'alert_sent': bool, 'in_descarga': bool}}
        self.next_pacote_id = 0
        self.max_etiqueta_gap = 8.0  # Tempo máximo sem etiqueta (8 segundos)
        self.min_etiqueta_conf = 0  # Confiança mínima para considerar etiqueta válida
        self.max_pacote_age = 5.0  # Tempo máximo sem ver um pacote antes de removê-lo
        self.max_pacote_lifetime_without_etiqueta = 10.0  # Tempo máximo de vida sem etiqueta antes de alertar

        self.messenger_alertas = KafkaMessenger(topic='alertas')

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)

        self.required_time = self.dados['required_times'][0]['spectingPacotes']-1
    
        if not 'feirinha' in procedure_name:
            self.max_etiqueta_gap = 20
        
        print(f'[PacoteTracker] Tempo para emissão de alerta de etiqueta: {self.max_etiqueta_gap}')

    def is_inside_roi(self, box, roi):
        x1, y1, x2, y2 = box
        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
        roi_x, roi_y, roi_w, roi_h = roi
        return (roi_x <= center_x <= roi_x + roi_w) and (roi_y <= center_y <= roi_y + roi_h)

    def get_center(self, box):
        x1, y1, x2, y2 = box
        return (x1 + x2) // 2, (y1 + y2) // 2

    def assign_pacote_id(self, box):
        """Atribui um ID único a cada pacote baseado em sua posição"""
        center_x, center_y = self.get_center(box)
        
        # Verifica se corresponde a um pacote existente
        for pacote_id, state in self.pacote_states.items():
            last_center = state['last_center']
            distance = ((center_x - last_center[0])**2 + (center_y - last_center[1])**2)**0.5
            if distance < 50:  # Threshold de distância em pixels
                return pacote_id
                
        # Se não encontrou correspondência, cria novo ID
        new_id = self.next_pacote_id
        self.next_pacote_id += 1
        return new_id

    def update_pacote_states(self, pacote_id, has_etiqueta, box, in_descarga):
        """Atualiza o estado de um pacote específico"""
        now = time.time()
        center = self.get_center(box)
        
        if pacote_id not in self.pacote_states:
            self.pacote_states[pacote_id] = {
                'first_seen': now,
                'last_seen': now,
                'has_etiqueta': has_etiqueta,
                'last_etiqueta_time': now if has_etiqueta else None,
                'last_center': center,
                'color': (0, 255, 0) if has_etiqueta else (0, 0, 255),
                'alert_sent': False,
                'in_descarga': in_descarga,
                'disappeared': False,
                'disappeared_time': None
            }
        else:
            state = self.pacote_states[pacote_id]
            state['last_seen'] = now
            state['last_center'] = center
            state['in_descarga'] = in_descarga
            state['disappeared'] = False  # Reset disappeared flag if we see it again
            
            if has_etiqueta:
                state['last_etiqueta_time'] = now
                state['has_etiqueta'] = True
                state['color'] = (0, 255, 0)  # Verde
                state['alert_sent'] = False  # Resetar alerta quando etiqueta é detectada
            else:
                # Só verifica alertas para pacotes na área de descarga
                if in_descarga:
                    # Verifica se ultrapassou o tempo máximo sem etiqueta
                    time_without_etiqueta = 0
                    
                    if state['last_etiqueta_time']:
                        # Pacote que já teve etiqueta mas perdeu
                        time_without_etiqueta = now - state['last_etiqueta_time']
                    else:
                        # Pacote que nunca teve etiqueta
                        time_without_etiqueta = now - state['first_seen']
                    
                    if time_without_etiqueta > self.max_etiqueta_gap:
                        state['has_etiqueta'] = False
                        state['color'] = (0, 0, 255)  # Vermelho
                        
                        # Envia alerta se ainda não foi enviado
                        if not state['alert_sent']:
                            self.send_etiqueta_alert(pacote_id, time_without_etiqueta)
                            state['alert_sent'] = True
        if len(self.pacote_states) > 50:  # Limite máximo de pacotes rastreados
            # Remove os mais antigos primeiro
            oldest_ids = sorted(self.pacote_states.keys(), 
                            key=lambda x: self.pacote_states[x]['last_seen'])[:10]
            for old_id in oldest_ids:
                del self.pacote_states[old_id]


    def send_etiqueta_alert(self, pacote_id, time_without):
        """Envia alerta sobre pacote sem etiqueta com throttling"""
        if not hasattr(self, '_last_alert_time'):
            self._last_alert_time = 0
        now = time.time()
        if now - self._last_alert_time < 2.0:  # Não envia mais de 1 alerta a cada 2 segundos
            return
        self._last_alert_time = now
        alert_msg = {
            "alerta": True,
            "tipo": "sem_etiqueta",
            "pacote_id": pacote_id,
            "mensagem": f"Pacote {pacote_id} está sem etiqueta há {time_without:.1f} segundos na área de descarga",
            "timestamp": time.time()
        }
        self.messenger_alertas.send_message(alert_msg)
        print(f"[ALERTA] Pacote {pacote_id} sem etiqueta por {time_without:.1f} segundos")

    def send_disappeared_alert(self, pacote_id, lifetime):
        """Envia alerta sobre pacote que desapareceu sem etiqueta após tempo significativo"""
        alert_msg = {
            "alerta": True,
            "tipo": "desaparecido_sem_etiqueta",
            "pacote_id": pacote_id,
            "mensagem": f"Pacote {pacote_id} desapareceu sem etiqueta após {lifetime:.1f} segundos de existência",
            "timestamp": time.time()
        }
        self.messenger_alertas.send_message(alert_msg)
        print(f"[ALERTA] Pacote {pacote_id} desapareceu sem etiqueta após {lifetime:.1f} segundos")
        
    def check_etiqueta_inside_pacote(self, pacote_box, etiqueta_boxes, etiqueta_confs):
        """Verifica se há etiquetas válidas dentro do pacote"""
        x1_p, y1_p, x2_p, y2_p = pacote_box
        for (x1_e, y1_e, x2_e, y2_e), conf in zip(etiqueta_boxes, etiqueta_confs):
            if conf < self.min_etiqueta_conf:
                continue
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
            if not self.last_detection_time:
                self.last_detection_time = time.time()
                self.start_time = time.time()
            frame = cv2.resize(frame, (640, 640))

            if time.time() - self.start_time > self.dados['timeouts'][0]['spectingPacotes']-1:
                self.statusPassoProduto = False
                json_to_send = {"Descarregar os produtos": self.statusPassoProduto}
                self.messenger_passos.send_message(json_to_send)
                self.isSpecting = False
                self.alertPassoProduto = "Timeout excedido para descarregamento de produtos."
                print("[Produto Tracker] Timeout excedido para descarregamento de produtos.") 
                json_alert = {"alerta": True}
                self.messenger_alertas.send_message(json_alert)               

            # Move the frame to the same device as the model
            # if self.device == 'cuda':
            #     frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0
            #     frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
            # else:
            frame_tensor = frame

            # Perform inference
            results = self.model(frame_tensor, verbose=False)
            
            produto_boxes = []
            produto_confs = []
            produto_labels = []
            etiqueta_boxes = []
            etiqueta_confs = []
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = round(box.conf[0].item(), 2)
                    cls = int(box.cls[0].item())
                    label = self.model.names[cls]

                    if label in self.produtos:
                        produto_boxes.append((x1, y1, x2, y2))
                        produto_confs.append(conf)
                        produto_labels.append(label)
                    elif label == "etiqueta":
                        etiqueta_boxes.append((x1, y1, x2, y2))
                        etiqueta_confs.append(conf)

            # Verifica detecções em ambos os ROIs
            roi_carga_detections = self.check_roi_detections(produto_boxes, produto_confs, self.roi_carga)
            roi_descarga_detections = self.check_roi_detections(produto_boxes, produto_confs, self.roi_descarga, self.min_confidence)

            if roi_carga_detections:
                self.last_detection_time = time.time()
            else:
                if time.time() - self.last_detection_time > self.required_time:
                    self.statusPassoProduto = True
                    json_to_send = {"Descarregar os produtos": self.statusPassoProduto}
                    self.messenger_passos.send_message(json_to_send)
                    self.isSpecting = False
                    print(f"[Produto Tracker] Nenhuma detecção nos ROIs por {self.required_time} segundos. Parando a inspeção.")

            now = time.time()
            to_remove = []
            
            #Lógica de desaparecimento de pacote
            for pid, state in self.pacote_states.items():
                # Verifica se o pacote desapareceu
                # if state['in_descarga']:
                    if now - state['last_seen'] > 1.0 and not state['disappeared']:  # 1 segundo sem ser visto
                        state['disappeared'] = True
                        state['disappeared_time'] = now
                        
                        # Verifica se desapareceu sem etiqueta após tempo suficiente
                        if not state['has_etiqueta']:
                            lifetime = now - state['first_seen']
                            # if lifetime >= self.max_pacote_lifetime_without_etiqueta:
                            #     self.send_disappeared_alert(pid, lifetime)
                    # Verifica se deve remover o pacote (tempo muito longo sem ser visto)
                    if now - state['last_seen'] > self.max_pacote_age:
                        to_remove.append(pid)
            for pid in to_remove:
                del self.pacote_states[pid]
                

            # Processa cada pacote detectado
            for idx, box in enumerate(produto_boxes):
                x1, y1, x2, y2 = box
                conf = produto_confs[idx]
                label = produto_labels[idx]
                
                in_carga = self.is_inside_roi(box, self.roi_carga)
                in_descarga = self.is_inside_roi(box, self.roi_descarga) and conf >= self.min_confidence
                
                if in_carga or in_descarga:
                    pacote_id = self.assign_pacote_id(box)
                    has_etiqueta = self.check_etiqueta_inside_pacote(box, etiqueta_boxes, etiqueta_confs)
                    self.update_pacote_states(pacote_id, has_etiqueta, box, in_descarga)
                    
                    # Obtém o estado atualizado
                    state = self.pacote_states.get(pacote_id, {'color': (0, 255, 0), 'has_etiqueta': False})
                    color = state['color']
                    
                    if in_descarga:
                        # Calcula tempo sem etiqueta
                        time_without = 0
                        if not state['has_etiqueta']:
                            if state['last_etiqueta_time']:
                                # Já teve etiqueta antes
                                time_without = now - state['last_etiqueta_time']
                            else:
                                # Nunca teve etiqueta
                                time_without = now - state['first_seen']
                            
                            status = f"SEM ETIQUETA ({time_without:.1f}s)"
                        else:
                            status = "COM ETIQUETA"
                        
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(frame, f"{label} {status} {conf}", (x1, y1 - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    elif in_carga:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                        cv2.putText(frame, f"{label} {conf}", (x1, y1 - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # Desenha etiquetas
            for idx, etiqueta_box in enumerate(etiqueta_boxes):
                x1, y1, x2, y2 = etiqueta_box
                conf = etiqueta_confs[idx]
                in_descarga = self.is_inside_roi(etiqueta_box, self.roi_descarga)
                if in_descarga:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(frame, f"Etiqueta {conf}", (x1, y1 - 10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # Desenha os ROIs
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
            
            # print(f"[DEBUG] Pacotes ativos: {len(self.pacote_states)}, Memória GPU: {torch.cuda.memory_allocated()/1e6:.2f}MB" if self.device == 'cuda' else "")
            
            if self.device == 'cuda':
                del frame_tensor
                torch.cuda.empty_cache()
            return frame
        except Exception as e:
            print(f"[PacoteTracker] Error processing frame: {e}")
            return frame