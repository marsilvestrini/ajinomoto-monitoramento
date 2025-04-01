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

class PalletTracker:
    def __init__(self, model_path, expected_color, expected_pallet_class):
        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[PalletTracker] Using device: {self.device}")

        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)
        
        self.messenger_passos = KafkaMessenger(topic='passos')
        self.messenger_alertas = KafkaMessenger(topic='alertas')
        self.expected_color = expected_color
        self.expected_pallet_class = expected_pallet_class
        self.isSpecting = True
        self.preSpect = True
        self.spectingColor = False  # Inicialmente desativado
        self.statusPassoCollor = False
        self.spectingPlastic = False
        self.statusPassoClassePallet = False
        self.PREDEFINED_COLORS = {
            "laranja": (0, 165, 255),
            "amarelo": (0, 255, 255),
            "azul": (255, 0, 0),
            "branco": (255, 255, 255),
        }
        self.roi = [215, 161, 120, 246]  # x, y, w, h
        self.start_time = None  # Para contagem de tempo
        self.timeout_start = None  # Para o tempo limite de 60 segundos

        self.alertPassoCollor = ''
        self.alertPassoClassePallet = ''

        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as arquivo:
            self.dados = json.load(arquivo)
        
        self.required_time_classe = self.dados['required_times'][0]['spectingPalletClass']-1  # Segundos necessários sem detecção para confirmar remoção
        self.required_time_color = self.dados['required_times'][0]['spectingPalletColor']-1  # Segundos necessários sem detecção para confirmar remoção


    def closest_color(self, rgb):
        min_distance = float("inf")
        closest_name = None

        for name, predefined_rgb in self.PREDEFINED_COLORS.items():
            distance = np.sqrt(
                (rgb[0] - predefined_rgb[0]) ** 2
                + (rgb[1] - predefined_rgb[1]) ** 2
                + (rgb[2] - predefined_rgb[2]) ** 2
            )
            if distance < min_distance:
                min_distance = distance
                closest_name = name

        return closest_name

    def get_dominant_color(self, frame, roi):
        x, y, w, h = roi
        roi_frame = frame[y:y+h, x:x+w]

        # Calcula a média dos valores de cor na ROI
        avg_color_per_row = np.mean(roi_frame, axis=0)
        avg_color = np.mean(avg_color_per_row, axis=0)

        # Converte para inteiros e retorna como tupla
        return self.closest_color(tuple(int(c) for c in avg_color))
            
    def process_video(self, frame):
        try:
            frame = cv2.resize(frame, (640, 640))
            
            # Move the frame to the same device as the model (if using CUDA)
            if self.device == 'cuda':
                frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0  # Normalize and move to GPU
                frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)  # Change shape to (1, 3, H, W)
            else:
                frame_tensor = frame  # Use the frame as-is for CPU

            # Primeiro, identifica qualquer objeto do modelo YOLO na imagem
            if self.preSpect:
                results = self.model(frame_tensor, verbose=False)
                frame = results[0].plot()

                # Verifica se alguma classe foi detectada
                for result in results:
                    for box in result.boxes:
                        cls = int(box.cls[0].item())
                        label = self.model.names[cls]

                        if "pallet" in label:
                            if self.start_time is None:
                                self.start_time = time.time()  # Inicia a contagem de tempo
                            else:
                                elapsed_time = time.time() - self.start_time
                                if elapsed_time >= 0.1:  # 2 segundos
                                    # print(f"[Pallet Tracker] Pallet detectado, iniciando inspeção.")
                                    self.start_time = None
                                    self.spectingColor = True  # Agora inicia a verificação de cor
                                    self.preSpect = False
                                    self.timeout_start = time.time()  # Inicia o tempo limite
                        else:
                            self.start_time = None  # Reseta o tempo se a classe não for a esperada

            # Verifica a cor do pallet
            if self.spectingColor:
                # Verifica o tempo limite 
                if time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingPalletColor']-1:
                    print("[Pallet Tracker] Tempo limite excedido para verificação de cor.")
                    self.alertPassoCollor = 'Cor esperada de pallet não identificada'
                    self.statusPassoCollor = False
                    json_to_send = {f"Posicionar o palete {self.expected_color} na área amarela (área de destino)": self.statusPassoCollor}
                    self.messenger_passos.send_message(json_to_send)
                    self.spectingColor = False
                    self.spectingPlastic = True
                    self.timeout_start = time.time()  # Reinicia o tempo limite para o próximo passo
                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)
                    if self.expected_pallet_class == "pallet_descoberto":
                        print(f"[Pallet Tracker] Classe de pallet esperada == descoberta, pulando etapa")
                        self.spectingPlastic = False
                        self.isSpecting = False ## if classe == descoberto jump step

                else:
                    dominant_color = self.get_dominant_color(frame, self.roi)
                    if self.expected_color == dominant_color:
                        if self.start_time is None:
                            self.start_time = time.time()  # Inicia a contagem de tempo
                        else:
                            elapsed_time = time.time() - self.start_time
                            if elapsed_time >= self.required_time_color: 
                                print(f"[Pallet Tracker] Cor final definida: {dominant_color}")
                                self.start_time = None
                                self.spectingColor = False
                                self.statusPassoCollor = True
                                json_to_send = {f"Posicionar o palete {self.expected_color} na área amarela (área de destino)": self.statusPassoCollor}
                                self.messenger_passos.send_message(json_to_send)
                                self.spectingPlastic = True
                                self.timeout_start = time.time()  # Reinicia o tempo limite para o próximo passo
                                if self.expected_pallet_class == "pallet_descoberto":
                                    print(f"[Pallet Tracker] Classe de pallet esperada == descoberta, pulando etapa")
                                    self.spectingPlastic = False
                                    self.isSpecting = False ## if classe == descoberto jump step
                    else:
                        self.start_time = None  # Reseta o tempo se a cor não for a esperada
            
            # Verifica a classe do pallet
            if self.spectingPlastic:
                # Verifica o tempo limite de 60 segundos
                if time.time() - self.timeout_start > self.dados['timeouts'][0]['spectingPalletClass']-1:
                    self.alertPassoClassePallet = 'Classe de Pallet esperada não encontrada'
                    print("[Pallet Tracker] Tempo limite excedido para verificação de classe.")
                    self.statusPassoClassePallet = False
                    json_to_send = {"Colocar uma camada de filme de cobertura sobre o palete plástico (vazio)": self.statusPassoClassePallet}
                    self.messenger_passos.send_message(json_to_send)
                    self.spectingPlastic = False
                    self.isSpecting = False
                    json_alert = {"alerta": True}
                    self.messenger_alertas.send_message(json_alert)
                else:
                    results = self.model(frame_tensor, verbose=False)
                    frame = results[0].plot()

                    for result in results:
                        for box in result.boxes:
                            cls = int(box.cls[0].item())
                            label = self.model.names[cls]

                            if label == self.expected_pallet_class:
                                if self.start_time is None:
                                    self.start_time = time.time()  # Inicia a contagem de tempo
                                else:
                                    elapsed_time = time.time() - self.start_time
                                    if elapsed_time >= self.required_time_classe: 
                                        print(f"[Pallet Tracker] Classe de pallet definida: {label}")
                                        self.start_time = None
                                        self.spectingPlastic = False
                                        print("[Pallet Tracker] Encerrando inspeção de pallet")
                                        self.statusPassoClassePallet = True
                                        if self.expected_pallet_class == 'pallet_coberto':
                                            json_to_send = {"Colocar uma camada de filme de cobertura sobre o palete plástico (vazio)": self.statusPassoClassePallet}
                                            self.messenger_passos.send_message(json_to_send)
                                        self.isSpecting = False
                            else:
                                self.start_time = None  # Reseta o tempo se a classe não for a esperada

            # Desenha a ROI no frame
            x, y, w, h = self.roi
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Verde

            return frame  # Retorna o frame processado  
        except Exception as e:
            print(f'[PalletTracker] Error processing frame: {e}')