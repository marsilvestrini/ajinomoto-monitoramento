# Usa a imagem base do Ubuntu 22.04
FROM ubuntu:22.04

# Instala dependências necessárias incluindo as bibliotecas do sistema para OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3.10-distutils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configura o python3.10 como padrão
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos necessários
COPY requirements.txt .
COPY api.py .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos (se necessário)
COPY . .

# Comando que será executado quando o container iniciar
CMD ["bash", "-c", "python -u api.py & tail -f /dev/null"]

# Expõe a porta da API
EXPOSE 5000