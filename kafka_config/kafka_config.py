from kafka import KafkaProducer, KafkaConsumer
import json
import time

class KafkaMessenger:
    def __init__(self, topic, bootstrap_servers='localhost:9092'):
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
    def __init__(self, topic, bootstrap_servers='localhost:9092'):
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),  # Desserializa o JSON
            auto_offset_reset='earliest',  # Começa a ler desde o início do tópico (se não houver offset commit)
            group_id='my-group',  # Define um grupo de consumidores
            enable_auto_commit=False  # Desabilita o commit automático do offset
        )
        self.topic = topic
    
    def listen(self):
        """
        Escuta mensagens no tópico Kafka e imprime o JSON recebido.
        """
        print(f"[KafkaListener] Aguardando mensagens no tópico '{self.topic}'...")
        try:
            for message in self.consumer:
                data = message.value
                print(f"[KafkaListener] JSON recebido: {data}")
                
                # Retorna a mensagem para ser processada
                yield data

            # self.commit()

        except Exception as e:
            print(f"[KafkaListener] Erro ao processar mensagem: {e}")
        finally:
            self.consumer.close()
    
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