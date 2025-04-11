from kafka_config import KafkaMessenger

messenger = KafkaMessenger(topic='cancelar_procedimentos')

json_to_send = {"procedimento": "pallet_fechado"}
messenger.send_message(json_to_send)


# messenger = KafkaMessenger(topic='alertas')

# json_to_send = {"alerta": True}
# messenger.send_message(json_to_send)

