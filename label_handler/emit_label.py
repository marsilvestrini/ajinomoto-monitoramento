import serial
from kafka_config_label import KafkaMessengerLabels, KafkaListenerLabels

def read_qr_code():
    """
    Função para ler QR Codes da porta serial e atualizar o valor da etiqueta.
    """
    ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)  # Ajuste a porta e baudrate conforme necessário
    print("Aguardando leitura do QR Code...")
    messenger_etiquetas = KafkaMessengerLabels(topic='etiquetas')
    messenger_labels = KafkaMessengerLabels(topic='labels')
    listener = KafkaListenerLabels(topic='etiquetas')
    try:
        while True:
            # print("Esperando QR code")
            qr_code = ser.readline().decode('utf-8').strip()
            if qr_code:
                print(f"QR CODE: {qr_code}")
                json_to_send = {"etiqueta": qr_code}
                messenger_etiquetas.send_message(json_to_send)
                messenger_labels.send_message(json_to_send)
    except KeyboardInterrupt:
        print("Encerrando leitura de QR Code...")
        ser.close()
    except Exception as e:
        print(f"Erro inesperado: {e}")
        ser.close()


if __name__ == "__main__":
    read_qr_code()