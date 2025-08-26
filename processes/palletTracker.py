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


class PalletTracker:
    def __init__(self, model_path, expected_color, expected_pallet_class):
        # Check if CUDA is available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[PalletTracker] Using device: {self.device}")

        # Load the YOLO model and move it to the appropriate device
        self.model = YOLO(model_path).to(self.device)

        self.messenger_passos = KafkaMessenger(topic="passos")
        self.messenger_alertas = KafkaMessenger(topic="alertas")
        self.expected_color = expected_color
        self.expected_pallet_class = expected_pallet_class
        self.isSpecting = True
        self.preSpect = False
        self.spectingColor = True
        self.statusPassoCollor = False
        self.spectingPlastic = False
        self.statusPassoClassePallet = False
        self.PREDEFINED_COLORS = {
            "laranja": (50, 90, 210),
            "amarelo": (10, 200, 220),
            "azul": (255, 0, 0),
            "branco": (200, 205, 200),
            "vazio": (146, 155, 153),
            "amarelo_coberto": (114, 221, 240),
            "verde_polpa": (114, 121, 217),
        }

        # self.roi_color = [215, 161, 120, 246]  # ROI para verificação de cor
        self.roi_color = [225, 205, 120, 246]  # x, y, w, h
        self.roi_plastic = [
            190,
            170,
            188,
            319,
        ]  # ROI compartilhada para preSpect e plastic
        self.start_time = None
        self.timeout_start = None

        self.alertPassoCollor = ""
        self.alertPassoClassePallet = ""

        with open(os.getenv("JSON_PATH"), "r", encoding="utf-8") as arquivo:
            self.dados = json.load(arquivo)

        self.required_time_classe = (
            self.dados["required_times"][0]["spectingPalletClass"] - 1
        )
        self.required_time_color = (
            self.dados["required_times"][0]["spectingPalletColor"] - 1
        )
    
    def skip(self, skipJustification):
        """
        Força o avanço da sub-etapa ATUAL do PalletTracker.
        - Se estiver verificando a cor, avança para a verificação da classe.
        - Se estiver verificando a classe, finaliza o tracker por completo.
        """
        
        if self.spectingColor:
            print("[PalletTracker] Avançando a etapa de verificação de COR via skip.")
            
            self.statusPassoCollor = True
            json_to_send_color = {
                f"Posicionar o palete {self.expected_color} na área amarela (área de destino)": self.statusPassoCollor,
                "skip": True,
                "justification": skipJustification
            }
            self.messenger_passos.send_message(json_to_send_color)

            self.spectingColor = False
            self.spectingPlastic = True
            
            self.start_time = None
            self.timeout_start = time.time()
            
            if self.expected_pallet_class == "pallet_descoberto":
                print("[PalletTracker] Próxima etapa (Classe Pallet) não é necessária, encerrando o tracker.")
                self.spectingPlastic = False
                self.isSpecting = False
            
        elif self.spectingPlastic:
            print("[PalletTracker] Avançando a etapa de verificação de CLASSE DE PALLET via skip.")

            if self.expected_pallet_class != "pallet_descoberto":
                self.statusPassoClassePallet = True
                json_to_send_plastic = {
                    "Colocar uma camada de filme de cobertura sobre o palete plástico (vazio)": self.statusPassoClassePallet,
                    "skip": True,
                    "justification": skipJustification
                }
                self.messenger_passos.send_message(json_to_send_plastic)
            
            self.spectingPlastic = False
            self.isSpecting = False

        else:
            print("[PalletTracker] Comando skip recebido, mas nenhuma sub-etapa ativa para avançar.")

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
        roi_frame = frame[y : y + h, x : x + w]
        avg_color_per_row = np.mean(roi_frame, axis=0)
        avg_color = np.mean(avg_color_per_row, axis=0)
        print("abv color: ", avg_color)
        return self.closest_color(tuple(int(c) for c in avg_color))

    def process_video(self, frame):
        try:
            if self.timeout_start is None:
                self.timeout_start = time.time()

            frame = cv2.resize(frame, (640, 640))

            # if self.device == 'cuda':
            #     frame_tensor = torch.from_numpy(frame).to(self.device).float() / 255.0
            #     frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
            # else:
            frame_tensor = frame

            output_frame = frame.copy()
            roi_x1, roi_y1 = self.roi_plastic[0], self.roi_plastic[1]
            roi_x2, roi_y2 = roi_x1 + self.roi_plastic[2], roi_y1 + self.roi_plastic[3]

            # Primeiro, identifica qualquer objeto do modelo YOLO na ROI específica
            if self.preSpect:
                results = self.model(frame_tensor, verbose=False)
                detected_in_roi = False

                # Verifica apenas detecções dentro da ROI
                for result in results:
                    for box in result.boxes:
                        cls = int(box.cls[0].item())
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        if (
                            x1 >= roi_x1
                            and y1 >= roi_y1
                            and x2 <= roi_x2
                            and y2 <= roi_y2
                        ):
                            label = self.model.names[cls]
                            print(label)
                            if "pallet" in label:
                                detected_in_roi = True
                                # Desenha apenas detecções dentro da ROI
                                color = (0, 255, 0)  # Verde
                                cv2.rectangle(
                                    output_frame,
                                    (int(x1), int(y1)),
                                    (int(x2), int(y2)),
                                    color,
                                    2,
                                )
                                cv2.putText(
                                    output_frame,
                                    label,
                                    (int(x1), int(y1) - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    color,
                                    2,
                                )

                if detected_in_roi:
                    self.spectingColor = True
                    self.preSpect = False
                    self.timeout_start = time.time()

                # Desenha a ROI para visualização
                cv2.rectangle(
                    output_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 0, 255), 2
                )
                cv2.putText(
                    output_frame,
                    "ROI Pre-Spect",
                    (roi_x1, roi_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )

            # Verifica a cor do pallet (usa ROI normal)
            if self.spectingColor:
                if self.start_time is None:
                    self.start_time = time.time()

                if (
                    time.time() - self.timeout_start
                    > self.dados["timeouts"][0]["spectingPalletColor"] - 1
                ):
                    print(
                        "[Pallet Tracker] Tempo limite excedido para verificação de cor."
                    )
                    self.alertPassoCollor = "Cor esperada de pallet não identificada"
                    self.statusPassoCollor = False
                    json_to_send = {
                        f"Posicionar o palete {self.expected_color} na área amarela (área de destino)": self.statusPassoCollor
                    }
                    self.messenger_passos.send_message(json_to_send)
                    self.spectingColor = False
                    self.spectingPlastic = True
                    self.timeout_start = time.time()

                    json_alert = {
                        "alerta": True,
                        "type": "info",
                        "message": "Tempo limite excedido para verificação de cor",
                    }
                    self.messenger_alertas.send_message(json_alert)

                    if os.getenv("SAVE_RESULTS"):
                        filename = os.path.join(
                            os.getenv("SAVE_PATH"), f"{datetime.now()}.jpg"
                        )
                        print(f"[Pallet Tracker] Saving file: {filename}")
                        cv2.imwrite(filename, frame)

                    if self.expected_pallet_class == "pallet_descoberto":
                        print(
                            f"[Pallet Tracker] Classe de pallet esperada == descoberta, pulando etapa"
                        )
                        self.spectingPlastic = False
                        self.isSpecting = False
                else:
                    dominant_color = self.get_dominant_color(frame, self.roi_color)
                    if self.expected_color == dominant_color:
                        elapsed_time = time.time() - self.start_time
                        if elapsed_time >= self.required_time_color:
                            print(
                                f"[Pallet Tracker] Cor final definida: {dominant_color}"
                            )
                            self.start_time = None
                            self.spectingColor = False
                            self.statusPassoCollor = True
                            json_to_send = {
                                f"Posicionar o palete {self.expected_color} na área amarela (área de destino)": self.statusPassoCollor
                            }
                            self.messenger_passos.send_message(json_to_send)
                            self.spectingPlastic = True
                            self.timeout_start = time.time()
                            if self.expected_pallet_class == "pallet_descoberto":
                                print(
                                    f"[Pallet Tracker] Classe de pallet esperada == descoberta, pulando etapa"
                                )
                                self.spectingPlastic = False
                                self.isSpecting = False
                    else:
                        self.start_time = None

                cv2.putText(
                    output_frame,
                    f"cor identificada: {dominant_color}",
                    (15, 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )
                # Desenha a ROI de cor (verde)
                x, y, w, h = self.roi_color
                cv2.rectangle(output_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(
                    output_frame,
                    "ROI Collor",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )

            # Verifica a classe do pallet (usa mesma ROI do preSpect)
            if self.spectingPlastic:
                if self.start_time is None:
                    self.start_time = time.time()

                if (
                    time.time() - self.timeout_start
                    > self.dados["timeouts"][0]["spectingPalletClass"] - 1
                ):
                    self.alertPassoClassePallet = (
                        "Classe de Pallet esperada não encontrada"
                    )
                    print(
                        "[Pallet Tracker] Tempo limite excedido para verificação de classe."
                    )
                    self.statusPassoClassePallet = False
                    json_to_send = {
                        "Colocar uma camada de filme de cobertura sobre o palete plástico (vazio)": self.statusPassoClassePallet
                    }
                    self.messenger_passos.send_message(json_to_send)
                    self.spectingPlastic = False
                    self.isSpecting = False
                    json_alert = {
                        "alerta": True,
                        "type": "info",
                        "message": "Tempo limite excedido para a detecção do pallet",
                    }
                    self.messenger_alertas.send_message(json_alert)

                    if os.getenv("SAVE_RESULTS"):
                        filename = os.path.join(
                            os.getenv("SAVE_PATH"), f"{datetime.now()}.jpg"
                        )
                        print(f"[Pallet Tracker] Saving file: {filename}")
                        cv2.imwrite(filename, frame)

                else:
                    results = self.model(frame_tensor, verbose=False)
                    detected_in_roi = False

                    # Filtra apenas detecções dentro da ROI
                    for result in results:
                        for box in result.boxes:
                            cls = int(box.cls[0].item())
                            x1, y1, x2, y2 = box.xyxy[0].tolist()

                            if (
                                x1 >= roi_x1
                                and y1 >= roi_y1
                                and x2 <= roi_x2
                                and y2 <= roi_y2
                            ):
                                label = self.model.names[cls]
                                if label == self.expected_pallet_class:
                                    detected_in_roi = True

                                    # Desenha apenas detecções dentro da ROI
                                color = (0, 255, 0)  # Verde
                                cv2.rectangle(
                                    output_frame,
                                    (int(x1), int(y1)),
                                    (int(x2), int(y2)),
                                    color,
                                    2,
                                )
                                cv2.putText(
                                    output_frame,
                                    label,
                                    (int(x1), int(y1) - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    color,
                                    2,
                                )

                    dominant_color = self.get_dominant_color(frame, self.roi_color)
                    cv2.putText(
                        output_frame,
                        f"cor identificada: {dominant_color}",
                        (15, 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        2,
                    )
                    if dominant_color == "amarelo_coberto":
                        detected_in_roi = True
                        print(
                            "[PalletTracker] (DEBUG) Detectado pela cor de pallet coberto coberta"
                        )

                    if detected_in_roi:
                        elapsed_time = time.time() - self.start_time
                        if elapsed_time >= self.required_time_classe:
                            print(
                                f"[Pallet Tracker] Classe de pallet definida: {self.expected_pallet_class}"
                            )
                            self.start_time = None
                            self.spectingPlastic = False
                            print("[Pallet Tracker] Encerrando inspeção de pallet")
                            self.statusPassoClassePallet = True
                            json_to_send = {
                                "Colocar uma camada de filme de cobertura sobre o palete plástico (vazio)": self.statusPassoClassePallet
                            }
                            self.messenger_passos.send_message(json_to_send)
                            self.isSpecting = False
                    else:
                        self.start_time = None

                # Desenha a ROI para visualização
                cv2.rectangle(
                    output_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 0, 255), 2
                )
                cv2.putText(
                    output_frame,
                    "ROI Plastic",
                    (roi_x1, roi_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )

            return output_frame

        except Exception as e:
            print(f"[PalletTracker] Error processing frame: {e}")
            return frame

