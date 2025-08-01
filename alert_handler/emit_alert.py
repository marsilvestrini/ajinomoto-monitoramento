from kafka_config_alert_test import KafkaMessenger
import time

def run_kafka_alert():
    """
    Função para rodar o Kafka em um thread separado.
    """
    # Cria uma instancia da classe que gerencia o alerta
    # Cria uma instância do KafkaListener
    kafka = KafkaMessenger(topic='alertas')
    json = {'alerta': True}
    kafka.send_message(json)
    
if __name__ == "__main__":
    while True:
        run_kafka_alert()
        time.sleep(5)