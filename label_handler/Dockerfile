# Usa a imagem base do Ubuntu 22.04
FROM ubuntu:22.04

# Atualiza o sistema e instala dependências básicas
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Adiciona o repositório para Python 3.10 e instala Python
RUN add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y python3.10 python3.10-distutils python3-pip

# Configura o Python 3.10 como padrão
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Copia todos os arquivos do diretório atual para /app no container
COPY . /app

# Define o diretório de trabalho
WORKDIR /app

# Instala as dependências do requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Comando para executar o script em loop
CMD ["bash", "-c", "while true; do python3 -u emit_label.py; done"]