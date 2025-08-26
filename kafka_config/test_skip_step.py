import requests
import json

# URL do endpoint no seu servidor Flask local
url = "http://localhost:5000/skip_step"

# Dados que serão enviados no corpo da requisição.
# A chave deve ser 'justification', como esperado pelo servidor.
payload = {
    "justification": "A etapa foi realizada manualmente pelo operador e confirmada visualmente."
}

# Cabeçalho indicando que estamos enviando dados em formato JSON.
# O parâmetro 'json' do requests.post já faz isso, mas é bom saber que ele existe.
headers = {
    "Content-Type": "application/json"
}

print(f"🚀 Enviando requisição POST para: {url}")
print(f"📄 Payload: {json.dumps(payload, indent=2)}")

try:
    # Realiza a requisição POST, enviando o dicionário 'payload' como JSON
    response = requests.post(url, json=payload, headers=headers)

    # Verifica se a requisição foi bem-sucedida (status code 2xx)
    response.raise_for_status() 

    # Imprime a resposta recebida do servidor
    print("\n✅ Resposta do Servidor:")
    print(f"Status Code: {response.status_code}")
    print(f"Corpo da Resposta: {response.json()}")

except requests.exceptions.ConnectionError as e:
    print(f"\n❌ Erro de Conexão: Não foi possível conectar ao servidor.")
    print("   Verifique se o seu servidor Flask está rodando em http://localhost:5000")

except requests.exceptions.HTTPError as e:
    print(f"\n❌ Erro HTTP: O servidor retornou um erro.")
    print(f"   Status Code: {e.response.status_code}")
    print(f"   Resposta do Servidor: {e.response.text}")

except Exception as e:
    print(f"\n❌ Ocorreu um erro inesperado: {e}")