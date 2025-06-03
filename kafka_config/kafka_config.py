from kafka import KafkaProducer, KafkaConsumer
import json
import time
import uuid

class KafkaMessenger:
    def __init__(self, topic, bootstrap_servers='kafka:9092'):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Serializa o JSON
        )
        self.topic = topic  # Tópico pode ser definido ao instanciar a classe
    
    def send_message(self, json_data):
        """
        Envia um JSON para o tópico Kafka.
        :param json_data: Dicionário Python contendo o JSON a ser enviado.
        """
        self.producer.send(self.topic, json_data)
        self.producer.flush()  # Garante que a mensagem seja enviada
        print(f"[KafkaMessenger] JSON enviado para o tópico '{self.topic}': {json_data}")

class KafkaMessengerLocal:
    def __init__(self, topic, bootstrap_servers='localhost:29092'):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Serializa o JSON
        )
        self.topic = topic  # Tópico pode ser definido ao instanciar a classe
    
    def send_message(self, json_data):
        """
        Envia um JSON para o tópico Kafka.
        :param json_data: Dicionário Python contendo o JSON a ser enviado.
        """
        self.producer.send(self.topic, json_data)
        self.producer.flush()  # Garante que a mensagem seja enviada
        print(f"[KafkaMessenger] JSON enviado para o tópico '{self.topic}': {json_data}")

class KafkaListener:
    def __init__(self, topic, bootstrap_servers='kafka:9092'):
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id='my-group-procedimentos',  # Nome fixo para controle
            enable_auto_commit=False,  # Commit manual habilitado
            # session_timeout_ms=30000,
            # heartbeat_interval_ms=10000,
            # max_poll_interval_ms=300000,
            max_poll_records=1  # Processa 1 mensagem por vez para commit preciso
        )
        self.topic = topic
        print(f"[KafkaListener] Iniciado (Tópico: {topic}, Grupo: {self.consumer.config['group_id']})")

    def listen(self):
        """Gera mensagens com commit manual após processamento bem-sucedido"""
        try:
            for message in self.consumer:
                try:
                    data = message.value
                    print(f"[KafkaListener] Nova mensagem [Offset: {message.offset}]")
                    yield data
                    
                    # Commit explícito após processamento
                    # self.consumer.commit()
                    # print(f"[KafkaListener] Commit realizado para offset {message.offset}")
                    
                except Exception as e:
                    print(f"[ERRO] Mensagem {message.offset} não processada: {str(e)}")
                    continue
                    
        except KeyboardInterrupt:
            print("\n[KafkaListener] Interrupção recebida")
        finally:
            self.close()
        
    def close(self):
        print(f"[KafkaListener] Closed Connection")
        self.consumer.close()

    def commit(self):
        print(f"[KafkaListener] Commit msg")
        self.consumer.commit()
        


if __name__ == "__main__":
    # Exemplo de uso
    topic = 'passos'

    # Enviar JSON
    messenger = KafkaMessenger(topic=topic)  # Define o tópico dinamicamente
    json_to_send = {"passo1": True}  # JSON no formato solicitado
    messenger.send_message(json_to_send)

    # Receber mensagens
    # listener = KafkaListener(topic=topic)  # Define o tópico dinamicamente
    # for message in listener.listen():
    #     # Aqui você pode adicionar lógica adicional para processar a mensagem
    #     pass
