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
from pg_config.pg_config import ProcedimentoManager
from handlers.handlers import AlertaHandler
from datetime import datetime
from video_config.video_capture_v2 import VideoCapture
from dotenv import load_dotenv
import os
from flask import Flask, Response
from threading import Thread, Lock
from queue import Queue
import time
import serial
from flask_cors import CORS, cross_origin
import logging

load_dotenv()

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# Buffer para armazenar os frames processados
frame_buffer = Queue(maxsize=1000)  # Ajuste o tamanho do buffer conforme necessário
frame_lock = Lock()  # Lock para garantir acesso seguro ao buffer

# Cria a pasta recordings se não existir
if not os.path.exists('recordings'):
    os.makedirs('recordings')

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

class VideoRecorder:
    def __init__(self):
        self.writer = None
        self.recording = False
        self.filename = None
        self.frame_size = None
    
    def start_recording(self, procedure_name):
        # Cria um nome de arquivo único baseado no timestamp e nome do procedimento
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"recordings/{procedure_name}_{timestamp}.avi"
        
        # Define o codec e cria o objeto VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.writer = cv2.VideoWriter(self.filename, fourcc, 20.0, self.frame_size)
        self.recording = True
        print(f"[VideoRecorder] Iniciando gravação em: {self.filename}")
    
    def write_frame(self, frame):
        if self.recording and self.writer is not None:
            self.writer.write(frame)
    
    def stop_recording(self):
        if self.recording and self.writer is not None:
            self.writer.release()
            self.recording = False
            print(f"[VideoRecorder] Gravação finalizada: {self.filename}")
            self.writer = None

class InspectProcedure:
    def __init__(self):
        self.video_path = os.getenv('VIDEO_PATH_START')

        # Carrega o JSON de procedimentos
        with open(os.getenv('JSON_PATH'), 'r', encoding='utf-8') as file:
            self.procedures_json = json.load(file)

        self.model_rede1 = os.getenv('MODEL_REDE1')
        self.model_rede2 = os.getenv('MODEL_REDE2')
        self.model_rede3 = os.getenv('MODEL_REDE3')
        self.model_rede4 = os.getenv('MODEL_REDE4')
        self.model_rede5 = os.getenv('MODEL_REDE5')

        self.expected_color = None
        self.expected_pallet_class = None
        self.expected_macacao_color = None

        # Initialize trackers
        self.palletTracker = PalletTracker(self.model_rede2, self.expected_color, self.expected_pallet_class)
        self.macacaoTracker = MacacaoTracker(self.model_rede3, self.expected_macacao_color)

        self.startTracker = StartTracker(self.model_rede1)
        self.pacoteTracker = PacoteTracker(self.model_rede1)
        self.stretchTracker = StretchTracker(self.model_rede4)
        self.finishTracker = FinishTracker(self.model_rede1)
        
        self.tracker_order = [self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]
        self.tracker_index = 0

        self.current_tracker = self.tracker_order[0]  # Começa com o PalletTracker

        # Definições db
        self.alerta_total = ""
        self.obs = ""
        self.current_procedure = None

        # Timestamps
        self.timestamp_inicio = None
        self.timestamp_fim = None

        # Initialize VideoCapture with a callback to process frames
        self.video_capture = VideoCapture(self.video_path, self.frame_process)
        
        # Initialize VideoRecorder
        self.video_recorder = VideoRecorder()

    def update_video_path(self):
        """
        Update the video path based on the current tracker.
        """
        tracker_name = self.current_tracker.__class__.__name__
        if tracker_name == "StartTracker":
            self.video_path = os.getenv('VIDEO_PATH_START')
        elif tracker_name == "MacacaoTracker":
            if self.expected_macacao_color == "macacao_branco":
                return
            self.video_path = os.getenv('VIDEO_PATH_MACACAO')
        elif tracker_name == "PalletTracker":
            self.video_path = os.getenv('VIDEO_PATH_PALLET')
        elif tracker_name == "PacoteTracker":
            self.video_path = os.getenv('VIDEO_PATH_PACOTE')
        elif tracker_name == "StretchTracker":
            self.video_path = os.getenv('VIDEO_PATH_STRETCH')
        elif tracker_name =='FinishTracker':
            self.video_path = os.getenv('VIDEO_PATH_FINISH')
        else:
            self.video_path = os.getenv('VIDEO_PATH_DEFAULT')

        # Reinitialize VideoCapture with the new video path
        self.video_capture.stop_capture()
        # Reinitialize VideoCapture with the new video path
        self.video_capture = VideoCapture(self.video_path, self.frame_process)
        self.video_capture.start_capture()

    def frame_process(self, frame):
        """
        Callback method to process each frame.
        """
        global frame_buffer

        # Verifica se o procedimento foi cancelado
        if CancelHandler.get_isCanceled_value():
            print("[InspectProcedure] Procedimento cancelado durante o processamento do frame.")
            self.cancel_procedure()
            return

        if not self.current_tracker.isSpecting:
            self.tracker_index += 1
            if self.tracker_index < len(self.tracker_order):
                self.current_tracker = self.tracker_order[self.tracker_index]
                print(f"[InspectProcedure] iniciando: {self.current_tracker}")
                self.update_video_path()  
            else:
                # self.video_capture.stop_capture()
                print("[InspectProcedure] Todos os trackers finalizados.")
                self.timestamp_fim = datetime.now()  # Captura o timestamp de fim
                self.save_on_db()
                self.video_recorder.stop_recording()
                run_kafka()
                return  # Retorna para continuar a escutar o Kafka

        # Processa o frame no tracker atual
        processed_frame = self.current_tracker.process_video(frame)
        
        # Se for o primeiro frame, define o tamanho do frame para o VideoWriter
        if self.video_recorder.frame_size is None:
            height, width = processed_frame.shape[:2]
            self.video_recorder.frame_size = (width, height)
        
        # Grava o frame processado
        self.video_recorder.write_frame(processed_frame)

        # Adiciona o frame processado ao buffer
        with frame_lock:
            if not frame_buffer.full():
                frame_buffer.put(processed_frame)

        return processed_frame

    def check_procedure(self, procedure_name):
        """
        Verifica se o nome do procedimento recebido do Kafka existe no JSON.
        """
        for procedure in self.procedures_json['procedimentos']:
            if procedure['nome'] == procedure_name:
                return True
        return False

    def get_procedure_info(self, procedure_name):
        """
        Retorna as informações do procedimento (expected_color e expected_pallet_class) com base no nome.
        """
        for procedure in self.procedures_json['procedimentos']:
            if procedure['nome'] == procedure_name:
                return procedure['info'][0]['expected_macacao_color'], procedure['info'][1]['expected_pallet_color'], procedure['info'][2]['expected_pallet_class'], eval(procedure['ordem'])
        return None, None, None, None

    def get_db_info(self, procedure_name):
        """
        Retorna as informações do procedimento (expected_color e expected_pallet_class) com base no nome.
        """
        for procedure in self.procedures_json['procedimentos']:
            if procedure['nome'] == procedure_name:
                return eval(procedure['db_command_etapas']), eval(procedure['db_command_alertas']) 
        return None, None
    
    def process_video_on_procedure(self, procedure_name):
        """
        Inicia o processamento do vídeo se o procedimento for válido.
        """
        if self.check_procedure(procedure_name):
            print(f"[InspectProcedure] Procedimento '{procedure_name}' encontrado. Iniciando processamento do vídeo...")
            self.current_procedure = procedure_name

            CancelHandler.set_isCanceled_value(False)

            # Zera o valor da etiqueta ao iniciar um novo procedimento
            EtiquetaHandler.set_quantidade_etiqueta_zero()
            EtiquetaHandler.set_valor_etiqueta(None)

            # Obtém as informações do procedimento
            self.expected_macacao_color, self.expected_color, self.expected_pallet_class, self.tracker_order = self.get_procedure_info(procedure_name)
            print(f"[InspectProcedure] expected_macacao_color: {self.expected_macacao_color}, expected_color: {self.expected_color}, expected_pallet_class: {self.expected_pallet_class}")

            # Atualiza o PalletTracker com os novos valores
            self.macacaoTracker = MacacaoTracker(self.model_rede3, self.expected_macacao_color) 
            self.palletTracker = PalletTracker(self.model_rede2, self.expected_color, self.expected_pallet_class)
            
            self.tracker_order[1] = self.macacaoTracker
            self.tracker_order[2] = self.palletTracker
            self.current_tracker = self.tracker_order[0]  # Define o current_tracker

            print("[InspectProcedure] Ordem:", self.tracker_order)

            # Captura o timestamp de início
            self.timestamp_inicio = datetime.now()
            
            # Inicia a gravação do vídeo
            self.video_recorder.start_recording(procedure_name)

            print(f"[InspectProcedure] iniciando: {self.current_tracker}")
            self.video_capture.start_capture()
            self.update_video_path()  
        else:
            print(f"[InspectProcedure] Procedimento '{procedure_name}' não encontrado no JSON.")

    def save_on_db(self):
        """
        Salva os dados do procedimento no banco de dados.
        """
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
            "id_procedimento": f"{self.current_procedure}"
        }
        print(f"[InspectProcedure] Saving on db:\n{procedimento}")
        manager = ProcedimentoManager()
        manager.adicionar_procedimento(**procedimento)
        manager.fechar_conexao()

    def cancel_procedure(self):
        """
        Cancela o procedimento atual e salva no banco de dados.
        """
        self.timestamp_fim = datetime.now()
        self.obs = "Operação cancelada."
        self.save_on_db()
        self.current_tracker = self.tracker_order[-1]
        self.current_tracker.isSpecting = False
        self.video_capture.stop_capture()
        self.video_recorder.stop_recording()
        print("[InspectProcedure] Procedimento cancelado.")
        run_kafka()

# Rota Flask para servir os frames do vídeo
@app.route('/video_feed')
@cross_origin()
def video_feed():
    def generate():
        global frame_buffer
        while True:
            frame = frame_buffer.get(block=True)  # Espera bloqueando até que um frame esteja disponível
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = jpeg.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    """
    Função para rodar o Flask em um thread separado.
    """
    app.run(host='0.0.0.0', port=5000, threaded=True)

def run_kafka():
    """
    Função para rodar o Kafka em um thread separado.
    """
    # Cria uma instância do InspectProcedure
    video = InspectProcedure()

    # Cria uma instância do KafkaListener para o tópico 'procedimento'
    kafka_listener = KafkaListener(topic='procedimento')

    # Escuta mensagens do Kafka
    for message in kafka_listener.listen():
        if isinstance(message, dict):
            procedure_name = message.get('procedimento')
            if procedure_name:
                print(f"[Main] Procedimento recebido: {procedure_name}")
                kafka_listener.commit()
                kafka_listener.close()
                video.process_video_on_procedure(procedure_name)
            else:
                print("[Main] Mensagem do Kafka não contém o campo 'procedimento'.")
        else:
            print(f"[Main] Mensagem recebida não é um dicionário. Tipo: {type(message)}, Conteúdo: {message}")

def run_kafka_cancel():
    """
    Função para rodar o Kafka em um thread separado, escutando o tópico 'cancelar'.
    """
    # Cria uma instância do KafkaListener para o tópico 'cancelar'
    kafka_cancel_listener = KafkaListener(topic='cancelar_procedimentos')

    # Escuta mensagens de cancelamento do Kafka
    for message in kafka_cancel_listener.listen():
        if isinstance(message, dict):
            print("[Main] Recebido comando de cancelamento.")
            kafka_cancel_listener.commit()
            CancelHandler.set_isCanceled_value(True)  # Sinaliza o cancelamento

def run_kafka_alert():
    """
    Função para rodar o Kafka em um thread separado.
    """
    # Cria uma instancia da classe que gerencia o alerta
    alerta_hander = AlertaHandler()
    # Cria uma instância do KafkaListener
    kafka_listener = KafkaListener(topic='alertas')

    # Escuta mensagens do Kafka
    for message in kafka_listener.listen():
        if isinstance(message, dict):
            alert_value = message.get('alerta')
            if alert_value:
                print(f"[Main] Alerta recebido: {alert_value}")
                alerta_hander.activate_outputs()
                kafka_listener.commit()
            else:
                print("[Main] Mensagem do Kafka não contém o campo 'alerta'.")
        else:
            print(f"[Main] Mensagem recebida não é um dicionário. Tipo: {type(message)}, Conteúdo: {message}")

def read_qr_code():
    """
    Função para ler QR Codes da porta serial e atualizar o valor da etiqueta.
    """
    ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)  # Ajuste a porta e baudrate conforme necessário
    print("Aguardando leitura do QR Code...")
    messenger_etiquetas = KafkaMessenger(topic='etiquetas')
    try:
        while True:
            qr_code = ser.readline().decode('utf-8').strip()  # Lê e decodifica a entrada serial
            if qr_code:
                # Atualiza o valor da etiqueta na instância de InspectProcedurex'
                print(f"QR CODE: {qr_code}")
                EtiquetaHandler.set_valor_etiqueta(qr_code)
                json_to_send = {"etiqueta": EtiquetaHandler.get_valor_etiqueta()}
                messenger_etiquetas.send_message(json_to_send)
                EtiquetaHandler.set_quantidade_etiqueta(1)
                print(f"[ReadQRcode] QR Code lido: {EtiquetaHandler.get_valor_etiqueta()}")
                print(f"[ReadQRcode] Número de QR Code lidos: {EtiquetaHandler.get_quantidade_etiqueta()}")
    except KeyboardInterrupt:
        print("Encerrando leitura de QR Code...")
        ser.close()

if __name__ == "__main__":
    # Cria a pasta recordings se não existir
    if not os.path.exists('recordings'):
        os.makedirs('recordings')

    # Inicia o Flask em um thread separado
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Inicia a leitura de QR Code em um thread separado
    qr_thread = Thread(target=read_qr_code)
    qr_thread.daemon = True
    qr_thread.start()

    # Inicia o Kafka em um thread separado para o tópico 'cancelar'
    kafka_cancel_thread = Thread(target=run_kafka_cancel)
    kafka_cancel_thread.daemon = True
    kafka_cancel_thread.start()

    kafka_alert_thread = Thread(target=run_kafka_alert)
    kafka_alert_thread.daemon = True
    kafka_alert_thread.start()
    
    run_kafka()