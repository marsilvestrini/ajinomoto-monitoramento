import psycopg2
from psycopg2 import sql, extras  # Importe o módulo extras
from datetime import datetime

class ProcedimentoManager:
    def __init__(self, dbname="ajinomoto_monitoramento", user="postgres", password="ajinomoto", host="localhost", port="5432"):
        """
        Construtor da classe. Inicializa a conexão com o banco de dados.
        """
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        self.cursor = self.conn.cursor()

    def adicionar_procedimento(self, timestamp_inicio, timestamp_fim, etiqueta, quantidade_etiquetas, alertas, etapa_1, etapa_2, etapa_3, etapa_4, etapa_5, etapa_6,etapa_7, observacoes, id_procedimento):
        """
        Adiciona um novo procedimento à tabela.
        """
        try:
            query = sql.SQL("""
                INSERT INTO procedimentos (
                    timestamp_inicio, timestamp_fim, etiqueta, quantidade_etiquetas,
                    alertas, etapa_1, etapa_2, etapa_3, etapa_4, etapa_5, etapa_6, etapa_7, observacoes, id_procedimento
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """)
            self.cursor.execute(query, (
                timestamp_inicio, timestamp_fim, etiqueta, quantidade_etiquetas,
                extras.Json(alertas),  # Converta o dicionário para JSONB
                etapa_1, etapa_2, etapa_3, etapa_4, etapa_5, etapa_6, etapa_7, observacoes, id_procedimento
            ))
            self.conn.commit()
            print("[PG Config] Procedimento registrado no db com sucesso!")
        except Exception as e:
            self.conn.rollback()
            print(f"[PG Config] Erro ao registrar procedimento no db: {e}")

    def fechar_conexao(self):
        """
        Fecha a conexão com o banco de dados.
        """
        self.cursor.close()
        self.conn.close()
        print("[PG Config] Conexão com o banco de dados fechada.")

# Exemplo de uso
if __name__ == "__main__":
    # Configurações do banco de dados
    dbname = "ajinomoto_monitoramento"
    user = "postgres"
    password = "postgres"
    host = "localhost"
    port = "5432"

    # Cria uma instância do ProcedimentoManager
    manager = ProcedimentoManager(dbname, user, password, host, port)

    # Dados do procedimento
    procedimento = {
        "timestamp_inicio": datetime(2023, 10, 1, 9, 0, 0),  # 2023-10-01 09:00:00
        "timestamp_fim": datetime(2023, 10, 1, 9, 5, 30),    # 2023-10-01 09:05:30
        "etiqueta": "teste",
        "quantidade_etiquetas": 0,
        "alertas": {"alerta":"teste"},  # Dicionário vazio
        "etapa_1": True,
        "etapa_2": True,
        "etapa_3": True,
        "etapa_4": True,
        "etapa_5": True,
        "etapa_6": None,
        "observacoes": "teste",
        "id_procedimento": "teste"
    }

    # Adiciona o procedimento ao banco de dados
    manager.adicionar_procedimento(**procedimento)

    # Fecha a conexão com o banco de dados
    manager.fechar_conexao()