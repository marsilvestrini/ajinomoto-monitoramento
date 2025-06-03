from kafka_config import KafkaMessengerLocal

messenger = KafkaMessengerLocal(topic='procedimento')

json_to_send = {"procedimento": "polpa"}
messenger.send_message(json_to_send)


# messenger = KafkaMessenger(topic='alertas')

# json_to_send = {"alerta": True}
# messenger.send_message(json_to_send)

