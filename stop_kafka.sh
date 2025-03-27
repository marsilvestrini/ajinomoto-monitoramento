#!/bin/bash

KAFKA_DIR="//opt/kafka"  # Caminho absoluto para o Kafka
ZOOKEEPER_CONFIG="$KAFKA_DIR/config/zookeeper.properties"
KAFKA_CONFIG="$KAFKA_DIR/config/server.properties"

# Função para verificar se um processo está rodando
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Função para parar um processo pelo nome
stop_process() {
    local process_name="$1"
    local process_desc="$2"
    echo "Verificando $process_desc..."
    if is_running "$process_name"; then
        echo "Parando $process_desc..."
        $KAFKA_DIR/bin/kafka-server-stop.sh > /dev/null 2>&1
        sleep 5  # Aguarda um pouco para garantir que o processo seja finalizado
        if is_running "$process_name"; then
            echo "$process_desc ainda está rodando. Forçando a parada..."
            pkill -f "$process_name"
            sleep 2
        fi
        echo "$process_desc parado com sucesso."
    else
        echo "$process_desc já está parado."
    fi
}

# Parar Kafka
stop_process "kafka.Kafka" "Kafka"

# Parar Zookeeper
stop_process "zookeeper" "Zookeeper"

echo "Kafka e Zookeeper parados com sucesso!"