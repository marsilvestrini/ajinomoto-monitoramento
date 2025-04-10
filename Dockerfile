# Use a imagem oficial do NVIDIA CUDA como base
FROM nvidia/cuda:12.1.1-base-ubuntu22.04

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

# Instala o PyTorch com CUDA primeiro (versão compatível com seu driver)
# Verifique a versão compatível em https://pytorch.org/get-started/locally/
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cu121

# Instala as demais dependências
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "-c", "while true; do python -u api.py; done"]
EXPOSE 5000