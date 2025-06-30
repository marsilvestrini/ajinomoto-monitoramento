
# Projeto de Processamento de Vídeo com Kafka e Flask

Este projeto processa vídeos em tempo real utilizando múltiplos trackers para inspeção, e integra Kafka para controle de procedimentos e cancelamentos, além de servir o vídeo processado via Flask.

---

## Tecnologias utilizadas

- Python
- Flask (para servir vídeo via HTTP)
- Kafka (para comunicação assíncrona de mensagens)
- OpenCV (para processamento de vídeo)
- Docker (para conteinerização opcional)
- Torch (PyTorch para modelos de detecção)

---

## Funcionamento básico

1. O sistema escuta mensagens Kafka em um tópico chamado `procedimento`, que indicam qual procedimento de inspeção iniciar.
2. Cada procedimento ativa uma sequência de trackers que processam frames capturados de um vídeo ou câmera.
3. O vídeo processado é armazenado em um buffer e servido pela aplicação Flask em `/video_feed` para visualização em tempo real.
4. É possível enviar uma mensagem no tópico `cancelar_procedimentos` para interromper o processo atual.
5. O sistema também escuta etiquetas (QR codes) em outro tópico Kafka e contabiliza a quantidade lida.
6. Ao fim de um procedimento ou cancelamento, dados são armazenados em banco via `ProcedimentoManager`.

---

## Como usar

### Pré-requisitos

- Python 3.8+
- Kafka configurado e rodando
- Docker (opcional)
- Variáveis de ambiente configuradas (`VIDEO_PATH_START`, `JSON_PATH`, etc)

### Rodando localmente

1. Instale as dependências:

```bash
pip install -r requirements.txt
pip install -r alert_handler/requirements.txt
```

2. Configure as variáveis de ambiente necessárias.

3. Inicie o projeto:

```bash
python api.py
```

4. Acesse o vídeo processado via browser em:  
```
http://localhost:5000/video_feed
```

### Rodando com Docker

1. Construa a imagem Docker:

```bash
docker build -t seu_nome_imagem .
```

2. Rode o container:

```bash
docker run -p 5000:5000 seu_nome_imagem
```

---

## Estrutura geral do projeto

- `api.py`: código principal, escuta Kafka e serve vídeo via Flask.
- `alert_handler/`: código para gerenciamento de alertas Kafka.
- `processes/`: módulos dos trackers que processam os frames.
- `video_config/`: configuração e captura dos vídeos.
- `pg_config/`: código para conexão e gravação no banco.
- `requirements.txt`: dependências principais do Python.


