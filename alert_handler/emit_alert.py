from alert_handler import AlertaHandler
from kafka_config_alert import KafkaListener

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
                print(f"[Main] Alerta recebido: {message}")
                alerta_hander.activate_outputs()
                kafka_listener.commit()
            else:
                print("[Main] Mensagem do Kafka não contém o campo 'alerta'.")
        else:
            print(f"[Main] Mensagem recebida não é um dicionário. Tipo: {type(message)}, Conteúdo: {message}")

if __name__ == "__main__":
    run_kafka_alert()