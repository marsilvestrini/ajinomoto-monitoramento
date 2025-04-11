# Use a imagem oficial do NVIDIA CUDA 11.8 como base
FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Instala dependências do sistema
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

# Configura o python padrão
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

WORKDIR /app

# Copia os arquivos necessários
COPY requirements.txt .
COPY api.py .

# Instala o PyTorch com CUDA 11.8 (versão compatível)
RUN pip install --default-timeout=100 --retries=10 --no-cache-dir \
    torch==2.0.1+cu118 torchvision==0.15.2+cu118 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# Instala as demais dependências
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "-c", "while true; do python -u api.py; done"]
EXPOSE 5000