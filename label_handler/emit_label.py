import serial
from kafika_config_label import KafkaMessenger

def read_qr_code():
    """
    Função para ler QR Codes da porta serial e atualizar o valor da etiqueta.
    """
    ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)  # Ajuste a porta e baudrate conforme necessário
    print("Aguardando leitura do QR Code...")
    messenger_etiquetas = KafkaMessenger(topic='etiquetas')
    messenger_labels = KafkaMessenger(topic='labels')
    try:
        while True:
            qr_code = ser.readline().decode('utf-8').strip()  # Lê e decodifica a entrada serial
            if qr_code:
                # Atualiza o valor da etiqueta na instância de InspectProcedurex'
                print(f"QR CODE: {qr_code}")
                json_to_send = {"etiqueta": qr_code}
                messenger_etiquetas.send_message(json_to_send)
                messenger_labels.send_message(json_to_send)
                print(f"[ReadQRcode] QR Code lido: {EtiquetaHandler.get_valor_etiqueta()}")
                print(f"[ReadQRcode] Número de QR Code lidos: {EtiquetaHandler.get_quantidade_etiqueta()}")
    except KeyboardInterrupt:
        print("Encerrando leitura de QR Code...")
        ser.close()