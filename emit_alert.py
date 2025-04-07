from kafka_config.kafka_config import KafkaListener
import modbus_tk.modbus_tcp as modbus_tk  # Import Modbus TCP library

# Modbus TCP client setup
MODBUS_SERVER_IP = '192.168.1.100'  # IP address of the Modbus device
MODBUS_SERVER_PORT = 502  # Default Modbus TCP port
MODBUS_COIL_ADDRESS = 0  # Address of the coil to control

class AlertaHander:
    def __init__(self):
        self.alert_state = False
        # Initialize Modbus TCP client
        self.modbus_client = modbus_tk.TcpMaster(host='192.168.1.100', port=502)
        self.modbus_client.set_timeout(5.0)  # Set a timeout for Modbus communication

    def process_alert(self, alert_value):
        self.alert_state = alert_value

        if self.alert_state:
            print(f"[AlertHander] Alert State: {self.alert_state}")
            try:
                # Write to Modbus coil (address 0, value 1)
                self.modbus_client.execute(
                    self.modbus_client.write_single_coil(0, 1)
                )
                print(f"[AlertHander] Coil at address {0} set to 1.")
            except Exception as e:
                print(f"[AlertHander] Error writing to Modbus coil: {e}")
            finally:
                self.alert_state = False  # Reset alert state

def run_kafka_alert():
    """
    Função para rodar o Kafka em um thread separado.
    """
    # Cria uma instancia da classe que gerencia o alerta
    alerta_hander = AlertaHander()
    # Cria uma instância do KafkaListener
    kafka_listener = KafkaListener(topic='alertas')

    # Escuta mensagens do Kafka
    for message in kafka_listener.listen():
        if isinstance(message, dict):
            alert_value = message.get('alerta')
            if alert_value:
                print(f"[Main] Alerta recebido: {alert_value}")
                alerta_hander.process_alert(alert_value)
            else:
                print("[Main] Mensagem do Kafka não contém o campo 'alerta'.")
        else:
            print(f"[Main] Mensagem recebida não é um dicionário. Tipo: {type(message)}, Conteúdo: {message}")

if __name__ == '__main__':
    run_kafka()