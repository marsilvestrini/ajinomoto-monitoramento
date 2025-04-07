#!/bin/bash

KAFKA_DIR="//opt/kafka_server"  # Caminho absoluto para o Kafka
ZOOKEEPER_CONFIG="$KAFKA_DIR/config/zookeeper.properties"
KAFKA_CONFIG="$KAFKA_DIR/config/server.properties"

# Função para verificar se um processo está rodando
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

echo "Verificando Zookeeper..."
if is_running "zookeeper"; then
    echo "Zookeeper já está rodando!"
else
    echo "Iniciando Zookeeper..."
    nohup $KAFKA_DIR/bin/zookeeper-server-start.sh $ZOOKEEPER_CONFIG > /tmp/zookeeper.log 2>&1 &
    ZOOKEEPER_PID=$!
    echo "Zookeeper iniciado com PID $ZOOKEEPER_PID"
    sleep 10  # Aguarda mais tempo para garantir que o Zookeeper tenha tempo suficiente para iniciar
fi

echo "Verificando Kafka..."
if is_running "kafka.Kafka"; then
    echo "Kafka já está rodando!"
else
    echo "Iniciando Kafka..."
    nohup $KAFKA_DIR/bin/kafka-server-start.sh $KAFKA_CONFIG > /tmp/kafka.log 2>&1 &
    KAFKA_PID=$!
    echo "Kafka iniciado com PID $KAFKA_PID"
    sleep 10  # Aguarda mais tempo para garantir que o Kafka tenha tempo suficiente para iniciar
fi

echo "Kafka e Zookeeper iniciados com sucesso!"
