import cv2
import json
from kafka_config.kafka_config import KafkaListener
from kafka_config.kafka_config import KafkaMessenger
from processes.pacoteTracker import PacoteTracker
from processes.palletTracker import PalletTracker
from processes.stretchTracker import StretchTracker
from processes.startTracker import StartTracker
from processes.macacaoTracker import MacacaoTracker
from processes.finishTracker import FinishTracker
from processes.labelPolpaTracker import LabelPolpaTracker
from processes.pacotePolpaTracker import PacotePolpaTracker
from pg_config.pg_config import ProcedimentoManager
from datetime import datetime
from video_config.video_capture_v2 import VideoCapture
from dotenv import load_dotenv
import os
from flask import Flask, Response
from threading import Thread, Lock
from queue import Queue, Empty
import time
import serial
from flask_cors import CORS, cross_origin
import logging
import torch

# Configura o PyTorch para melhor performance se a GPU for compatível
torch.backends.cudnn.enabled = True
torch.backends.cudnn.benchmark = True

load_dotenv()

# --- CONFIGURAÇÃO DE LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__)
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

# Buffer para armazenar os frames processados para o streaming
frame_buffer = Queue(maxsize=10000)
frame_lock = Lock()

# Cria a pasta de gravações se não existir
if not os.path.exists("recordings"):
    os.makedirs("recordings")

# --- CLASSES DE MANIPULAÇÃO DE ESTADO ---


class CancelHandler:
    isCanceled = False

    @classmethod
    def get_isCanceled_value(cls):
        return cls.isCanceled

    @classmethod
    def set_isCanceled_value(cls, new_isCanceled_value):
        cls.isCanceled = new_isCanceled_value


class EtiquetaHandler:
    quantidade_etiqueta = 0
    valor_etiqueta = None

    @classmethod
    def set_valor_etiqueta(cls, new_valor_etiqueta):
        cls.valor_etiqueta = new_valor_etiqueta

    @classmethod
    def set_quantidade_etiqueta(cls, new_quantidade_etiqueta):
        cls.quantidade_etiqueta += new_quantidade_etiqueta

    @classmethod
    def get_valor_etiqueta(cls):
        return cls.valor_etiqueta

    @classmethod
    def get_quantidade_etiqueta(cls):
        return cls.quantidade_etiqueta

    @classmethod
    def set_quantidade_etiqueta_zero(cls):
        cls.quantidade_etiqueta = 0


# --- CLASSE PRINCIPAL DE ORQUESTRAÇÃO ---


class InspectProcedure:
    def __init__(self):
        self.video_path = os.getenv("VIDEO_PATH_START")

        with open(os.getenv("JSON_PATH"), "r", encoding="utf-8") as file:
            self.procedures_json = json.load(file)

        self.model_paths = {
            "rede1": os.getenv("MODEL_REDE1"),
            "rede2": os.getenv("MODEL_REDE2"),
            "rede3": os.getenv("MODEL_REDE3"),
            "rede4": os.getenv("MODEL_REDE4"),
            "rede5": os.getenv("MODEL_REDE5"),
            "rede6": os.getenv("MODEL_REDE6"),
        }

        self.expected_color = None
        self.expected_pallet_class = None
        self.expected_macacao_color = None

        self.alerta_total = ""
        self.obs = ""
        self.current_procedure = None
        self.timestamp_inicio = None
        self.timestamp_fim = None

        self.tracker_order = []
        self.tracker_index = -1
        self.current_tracker = None  # Nenhum tracker carregado inicialmente

        self.video_capture = VideoCapture(self.video_path, self.frame_process)

    def create_tracker_by_name(self, tracker_name):
        """Cria uma instância do tracker com base no seu nome (string)."""
        logging.info(f"[GPU Manager] Carregando modelo para: {tracker_name}")
        if tracker_name == "StartTracker":
            return StartTracker(self.model_paths["rede1"])
        elif tracker_name == "MacacaoTracker":
            return MacacaoTracker(
                self.model_paths["rede3"], self.expected_macacao_color
            )
        elif tracker_name == "PalletTracker":
            return PalletTracker(
                self.model_paths["rede2"],
                self.expected_color,
                self.expected_pallet_class,
            )
        elif tracker_name == "PacoteTracker":
            return PacoteTracker(self.model_paths["rede1"], self.current_procedure)
        elif tracker_name == "StretchTracker":
            return StretchTracker(self.model_paths["rede4"])
        elif tracker_name == "FinishTracker":
            return FinishTracker(self.model_paths["rede1"])
        elif tracker_name == "LabelPolpaTracker":
            return LabelPolpaTracker(self.model_paths["rede6"])
        elif tracker_name == "PacotePolpaTracker":
            return PacotePolpaTracker(self.model_paths["rede1"])
        else:
            raise ValueError(f"Tracker desconhecido: {tracker_name}")

    def update_video_path(self):
        """Atualiza o caminho do vídeo com base no tracker atual."""
        if self.current_tracker is None:
            return

        tracker_name = self.current_tracker.__class__.__name__
        if tracker_name == "StartTracker":
            self.video_path = os.getenv("VIDEO_PATH_START")
        elif tracker_name == "MacacaoTracker":
            if self.expected_macacao_color == "macacao_branco":
                return
            self.video_path = os.getenv("VIDEO_PATH_MACACAO")
        elif tracker_name == "PalletTracker":
            self.video_path = os.getenv("VIDEO_PATH_PALLET")
        elif tracker_name == "PacoteTracker":
            self.video_path = os.getenv("VIDEO_PATH_PACOTE")
        elif tracker_name == "StretchTracker":
            self.video_path = os.getenv("VIDEO_PATH_STRETCH")
        elif tracker_name == "FinishTracker":
            self.video_path = os.getenv("VIDEO_PATH_FINISH")
        elif tracker_name == "LabelPolpaTracker":
            self.video_path = os.getenv("VIDEO_PATH_LABEL")
        elif tracker_name == "PacotePolpaTracker":
            self.video_path = os.getenv("VIDEO_PATH_PACOTE_POLPA")
        else:
            self.video_path = os.getenv("VIDEO_PATH_DEFAULT")

        self.video_capture.stop_capture()
        self.video_capture = VideoCapture(self.video_path, self.frame_process)
        self.video_capture.start_capture()

    def frame_process(self, frame):
        """Callback para processar cada frame, gerenciando o ciclo de vida dos trackers."""
        global frame_buffer

        if CancelHandler.get_isCanceled_value():
            logging.warning(
                "[InspectProcedure] Procedimento cancelado durante o processamento do frame."
            )
            self.cancel_procedure()
            return

        if self.current_tracker is None or not self.current_tracker.isSpecting:
            if self.current_tracker is not None:
                tracker_name = type(self.current_tracker).__name__
                logging.info(f"[GPU Manager] Descarregando modelo de: {tracker_name}")
                del self.current_tracker
                torch.cuda.empty_cache()  # Limpa o cache da GPU
            self.tracker_index += 1

            if self.tracker_index < len(self.tracker_order):
                next_tracker_name = self.tracker_order[self.tracker_index]
                self.current_tracker = self.create_tracker_by_name(next_tracker_name)
                self.update_video_path()
            else:
                self.video_capture.stop_capture()
                logging.info("[InspectProcedure] Todos os trackers finalizados.")
                self.timestamp_fim = datetime.now()
                self.save_on_db()
                time.sleep(3)
                os._exit(0)
                return  # Finaliza a execução

        processed_frame = self.current_tracker.process_video(frame)

        with frame_lock:
            if not frame_buffer.full():
                frame_buffer.put(processed_frame)

        return processed_frame

    def get_procedure_info(self, procedure_name):
        """Retorna as informações do procedimento com base no nome."""
        for procedure in self.procedures_json["procedimentos"]:
            if procedure["nome"] == procedure_name:
                ordem_str = procedure[
                    "ordem"
                ]  # Ex: "[self.startTracker, self.macacaoTracker]"

                sanitized_str = (
                    ordem_str.strip("[]").replace("self.", "").replace(" ", "")
                )

                tracker_instance_names = sanitized_str.split(",")

                ordem = [
                    name[0].upper() + name[1:]
                    for name in tracker_instance_names
                    if name
                ]

                return (
                    procedure["info"][0]["expected_macacao_color"],
                    procedure["info"][1]["expected_pallet_color"],
                    procedure["info"][2]["expected_pallet_class"],
                    ordem,
                )
        return None, None, None, None

    def get_db_info(self, procedure_name):
        """Retorna os comandos para salvar no banco de dados."""
        for procedure in self.procedures_json["procedimentos"]:
            if procedure["nome"] == procedure_name:
                return eval(procedure["db_command_etapas"]), eval(
                    procedure["db_command_alertas"]
                )
        return None, None

    def process_video_on_procedure(self, procedure_name):
        """Inicia o processamento de vídeo para um procedimento válido."""
        if any(
            proc["nome"] == procedure_name
            for proc in self.procedures_json["procedimentos"]
        ):
            logging.info(
                f"[InspectProcedure] Procedimento '{procedure_name}' encontrado. Iniciando processamento."
            )
            self.current_procedure = procedure_name

            CancelHandler.set_isCanceled_value(False)
            EtiquetaHandler.set_quantidade_etiqueta_zero()
            EtiquetaHandler.set_valor_etiqueta(None)
            (
                self.expected_macacao_color,
                self.expected_color,
                self.expected_pallet_class,
                tracker_names_order,
            ) = self.get_procedure_info(procedure_name)

            if "polpa" in procedure_name:
                tracker_names_order[3] = "PacotePolpaTracker"
            else:
                tracker_names_order[3] = "PacoteTracker"

            self.tracker_order = tracker_names_order

            logging.info(f"[InspectProcedure] Ordem de execução: {self.tracker_order}")

            self.tracker_index = -1
            self.current_tracker = None

            self.timestamp_inicio = datetime.now()

            self.video_capture.start_capture()
        else:
            logging.error(
                f"[InspectProcedure] Procedimento '{procedure_name}' não encontrado no JSON."
            )

    def save_on_db(self):
        """Salva os dados do procedimento no banco de dados."""
        db_command_etapas, db_command_alertas = self.get_db_info(self.current_procedure)
        self.alerta_total = db_command_alertas

        procedimento = {
            "timestamp_inicio": self.timestamp_inicio,
            "timestamp_fim": self.timestamp_fim,
            "etiqueta": f"{EtiquetaHandler.get_valor_etiqueta()}",
            "quantidade_etiquetas": EtiquetaHandler.get_quantidade_etiqueta(),
            "alertas": {"alerta": f"{self.alerta_total}"},
            "etapa_1": db_command_etapas[0],
            "etapa_2": db_command_etapas[1],
            "etapa_3": db_command_etapas[2],
            "etapa_4": db_command_etapas[3],
            "etapa_5": db_command_etapas[4],
            "etapa_6": db_command_etapas[5],
            "etapa_7": db_command_etapas[6],
            "observacoes": f"{self.obs}",
            "id_procedimento": f"{self.current_procedure}",
        }
        logging.info(
            f"[InspectProcedure] Salvando no banco de dados:\n{json.dumps(procedimento, indent=2, default=str)}"
        )
        manager = ProcedimentoManager()
        manager.adicionar_procedimento(**procedimento)
        manager.fechar_conexao()

    def cancel_procedure(self):
        """Cancela o procedimento atual e salva seu estado."""
        self.timestamp_fim = datetime.now()
        self.obs = "Operação cancelada."
        self.save_on_db()

        if self.current_tracker:
            self.current_tracker.isSpecting = False

        self.video_capture.stop_capture()
        logging.info("[InspectProcedure] Procedimento cancelado e salvo.")
        os._exit(0)


# --- ROTAS FLASK E THREADS ---


@app.route("/video_feed")
@cross_origin()
def video_feed():
    def generate():
        global frame_buffer
        while True:
            try:
                frame = frame_buffer.get(block=True, timeout=0.1)
                ret, jpeg = cv2.imencode(".jpg", frame)
                if ret:
                    frame_bytes = jpeg.tobytes()
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n\r\n"
                    )
            except Empty:
                time.sleep(0.05)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


def run_flask():
    """Inicia o servidor Flask em uma thread separada."""
    app.run(host="0.0.0.0", port=5000, threaded=True)


def run_kafka():
    """Inicia o consumidor Kafka para o tópico de procedimentos."""
    video = InspectProcedure()
    kafka_listener = KafkaListener(topic="procedimento")
    logging.info("[Main] Aguardando mensagens do Kafka no tópico 'procedimento'...")
    for message in kafka_listener.listen():
        if isinstance(message, dict):
            procedure_name = message.get("procedimento")
            if procedure_name:
                logging.info(f"[Main] Procedimento recebido: {procedure_name}")
                kafka_listener.commit()
                video.process_video_on_procedure(procedure_name)
                kafka_listener.close()
                break  # Sai do loop após receber e iniciar um procedimento
            else:
                logging.warning(
                    "[Main] Mensagem Kafka não contém o campo 'procedimento'."
                )
        else:
            logging.warning(f"[Main] Mensagem recebida não é um dicionário: {message}")


def run_kafka_cancel():
    """Inicia o consumidor Kafka para o tópico de cancelamento."""
    kafka_cancel_listener = KafkaListener(topic="cancelar_procedimentos")
    logging.info(
        "[Main] Aguardando mensagens do Kafka no tópico 'cancelar_procedimentos'..."
    )
    for message in kafka_cancel_listener.listen():
        if isinstance(message, dict):
            logging.info("[Main] Recebido comando de cancelamento.")
            kafka_cancel_listener.commit()
            CancelHandler.set_isCanceled_value(True)
            time.sleep(5)
            os._exit(0)


def run_etiquetas_listener():
    """Inicia o consumidor Kafka para o tópico de etiquetas."""
    kafka_etiquetas_listener = KafkaListener(topic="labels")
    logging.info("[Main] Aguardando mensagens do Kafka no tópico 'labels'...")
    for message in kafka_etiquetas_listener.listen():
        if isinstance(message, dict):
            qr_code = message.get("etiqueta")
            if qr_code:
                logging.info(f"[MAIN] QR CODE LIDO: {qr_code}")
                EtiquetaHandler.set_valor_etiqueta(qr_code)
                EtiquetaHandler.set_quantidade_etiqueta(1)


if __name__ == "__main__":
    logging.info("[Main] Iniciando aplicação...")

    # Inicia o Flask em uma thread separada
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Inicia o consumidor Kafka para cancelamento em uma thread separada
    kafka_cancel_thread = Thread(target=run_kafka_cancel)
    kafka_cancel_thread.daemon = True
    kafka_cancel_thread.start()

    # Opcional: Inicia o consumidor para etiquetas
    # qr_thread = Thread(target=run_etiquetas_listener)
    # qr_thread.daemon = True
    # qr_thread.start()

    # Inicia o consumidor principal do Kafka no thread principal
    run_kafka()

