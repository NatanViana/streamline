import pymysql
import pandas as pd
from fpdf import FPDF
import os
import duckdb
import streamlit as st
import ssl
import base64
import tempfile
from functools import lru_cache
from google.cloud import storage

def manual_load_dotenv(path="db/env.env"):
    if not os.path.exists(path):
        print("Arquivo inexistente")
        return

    with open(path) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value
               
# rodar no Localhost
#manual_load_dotenv()
#print("Host do banco:", os.getenv("GCS_KEY_BASE64"))

@lru_cache(maxsize=1)
def get_gcs_client():
    key_base64 = os.getenv("GCS_KEY_BASE64")
    #print(key_base64)
    key_bytes = base64.b64decode(key_base64)

    with tempfile.NamedTemporaryFile(delete=False) as temp_key:
        temp_key.write(key_bytes)
        temp_key_path = temp_key.name

    return storage.Client.from_service_account_json(temp_key_path)

def upload_para_gcs(bucket_name, blob_path, uploaded_file):
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_file(uploaded_file, rewind=True)
    return f"gs://{bucket_name}/{blob_path}"

def listar_arquivos_do_cliente(bucket_name, prefixo):
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    return list(bucket.list_blobs(prefix=prefixo))

# 🔐 Cria um contexto SSL a partir do certificado codificado em base64
@lru_cache(maxsize=1)
def get_ssl_context_from_secrets():
    ca_base64 = os.getenv("MYSQL_SSL_CA_BASE64")  # ou use st.secrets["MYSQL_SSL_CA_BASE64"]
    ca_bytes = base64.b64decode(ca_base64)

    # Salva em arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False) as ca_file:
        ca_file.write(ca_bytes)
        ca_path = ca_file.name

    # Configura contexto SSL
    ssl_context = ssl.create_default_context(cafile=ca_path)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    return ssl_context


# 🔁 Cria instância DuckDB in-memory
def get_duckdb():
    return duckdb.connect(database=':memory:')
# 🔁 Conexão com MySQL (persistência)
def get_mysql_conn():
    ssl_ctx = get_ssl_context_from_secrets()
    return pymysql.connect(
        host=os.getenv("host"),
        user=os.getenv("username"),
        password=os.getenv("password"),
        port=int(os.getenv("port")),
        database=os.getenv("database"),
        cursorclass=pymysql.cursors.DictCursor,
        ssl={'ssl': ssl_ctx}
    )


def criar_tabelas():
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psicologos (
                    id BIGINT PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS login (
                    id BIGINT PRIMARY KEY,
                    usuario VARCHAR(100) NOT NULL UNIQUE,
                    senha VARCHAR(255) NOT NULL,
                    funcao VARCHAR(50) NOT NULL,
                    psicologo_responsavel BIGINT,
                    privilegio BOOLEAN,
                    FOREIGN KEY (psicologo_responsavel) REFERENCES psicologos(id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id BIGINT PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL,
                    valor_sessao DOUBLE NOT NULL,
                    psicologo_responsavel BIGINT,
                    FOREIGN KEY (psicologo_responsavel) REFERENCES psicologos(id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessoes (
                    id BIGINT PRIMARY KEY,
                    cliente_id BIGINT,
                    data DATE NOT NULL,
                    hora TIME NOT NULL,
                    valor DOUBLE NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    cobrar BOOLEAN,
                    pagamento BOOLEAN,
                    nota_fiscal VARCHAR(50),
                    conteudo TEXT,
                    objetivo TEXT,
                    material TEXT,
                    atividade_casa TEXT,
                    emocao_entrada BIGINT,
                    emocao_saida BIGINT,
                    proxima_sessao TEXT,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
                );
            """)

        conn.commit()

# --------------------------------
# INSERT / UPDATE / DELETE: MySQL
# --------------------------------

def adicionar_psicologo(nome):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM psicologos WHERE nome = %s", (nome,))
            if cursor.fetchone()['count']:
                # mantém o comportamento anterior (lança erro ao tentar criar duplicado)
                raise ValueError("Psicólogo já cadastrado.")
            cursor.execute("SELECT MAX(id) AS max_id FROM psicologos")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            cursor.execute("INSERT INTO psicologos (id, nome) VALUES (%s, %s)", (novo_id, nome))
        conn.commit()

def adicionar_usuario(usuario, senha, funcao, psicologo_responsavel, privilegio):
    """
    - Se o login já existir e funcao == 'Psicóloga': PROMOVE (update) o usuário existente,
      sem alterar a senha; define psicologo_responsavel = próprio id de psicóloga e privilegio=1.
    - Se o login já existir e funcao != 'Psicóloga': lança 'Usuário já cadastrado.'
    - Se não existir: cria normalmente; para Psicóloga, garante o id próprio de psicóloga e usa como responsável.
    """
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            # Existe algum login com esse usuario?
            cursor.execute("SELECT * FROM login WHERE usuario = %s LIMIT 1", (usuario,))
            existente = cursor.fetchone()

            # Helper: get-or-create de psicólogo usando a MESMA conexão/cursor
            def _get_or_create_psicologo_id(nome: str) -> int:
                cursor.execute("SELECT id FROM psicologos WHERE nome = %s LIMIT 1", (nome,))
                row = cursor.fetchone()
                if row:
                    return row["id"]
                # cria novo id pelo seu padrão MAX+1
                cursor.execute("SELECT MAX(id) AS max_id FROM psicologos")
                novo_pid = (cursor.fetchone()["max_id"] or 0) + 1
                cursor.execute("INSERT INTO psicologos (id, nome) VALUES (%s, %s)", (novo_pid, nome))
                return novo_pid

            if existente:
                # Usuário já existe
                if funcao == "Psicóloga":
                    # 1) Garante/Cria psicóloga com esse nome (mesma conexão!)
                    psicologo_id = _get_or_create_psicologo_id(usuario)

                    # 2) PROMOÇÃO: atualiza o login existente (NÃO altera senha)
                    cursor.execute("""
                        UPDATE login
                           SET funcao = 'Psicóloga',
                               psicologo_responsavel = %s,
                               privilegio = 1
                         WHERE id = %s
                    """, (psicologo_id, existente['id']))
                    conn.commit()
                    return
                else:
                    # Mantém regra atual para duplicidade de assistente (ou outra função)
                    raise ValueError("Usuário já cadastrado.")

            # --- Novo usuário (não existia) ---
            if funcao == "Psicóloga":
                # Garante/Cria psicóloga e usa o próprio id como responsável (mesma conexão!)
                psicologo_id = _get_or_create_psicologo_id(usuario)
                psicologo_responsavel_final = psicologo_id
            else:
                # Assistente: usa o responsável vindo do front (validação mínima)
                if not psicologo_responsavel:
                    raise ValueError("Selecione o Psicólogo responsável.")
                psicologo_responsavel_final = psicologo_responsavel

            # Gera novo id para login (mantendo seu padrão MAX+1)
            cursor.execute("SELECT MAX(id) AS max_id FROM login")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1

            # Criação exige senha; se vier vazia/None, rejeita
            if senha is None or str(senha).strip() == "":
                raise ValueError("Senha obrigatória para criação de novo usuário.")

            cursor.execute("""
                INSERT INTO login (id, usuario, senha, funcao, psicologo_responsavel, privilegio)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (novo_id, usuario, senha, funcao, psicologo_responsavel_final, privilegio))

        conn.commit()

def adicionar_cliente(nome, valor_sessao, psicologo_responsavel):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM clientes WHERE nome = %s", (nome,))
            if cursor.fetchone()['count']:
                raise ValueError("Cliente já cadastrado.")
            cursor.execute("SELECT MAX(id) AS max_id FROM clientes")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            cursor.execute("""
                INSERT INTO clientes (id, nome, valor_sessao, psicologo_responsavel)
                VALUES (%s, %s, %s, %s)
            """, (novo_id, nome, valor_sessao, psicologo_responsavel))
        conn.commit()

def adicionar_sessao(cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,conteudo, objetivo, material, atividade_casa, emocao_entrada, emocao_saida, proxima_sessao):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS count FROM sessoes
                WHERE cliente_id = %s AND data = %s AND hora = %s
            """, (cliente_id, data, hora))
            if cursor.fetchone()['count']:
                raise ValueError("Sessão já registrada para este cliente neste horário.")
            
            cursor.execute("SELECT MAX(id) AS max_id FROM sessoes")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            
            cursor.execute("""
                INSERT INTO sessoes (
                    id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,
                    conteudo, objetivo, material, atividade_casa, emocao_entrada, emocao_saida, proxima_sessao
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                novo_id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,
                conteudo, objetivo, material, atividade_casa, emocao_entrada, emocao_saida, proxima_sessao
            ))
        conn.commit()

def excluir_cliente(cliente_id):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM sessoes WHERE cliente_id = %s", (cliente_id,))
            cursor.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
        conn.commit()

def excluir_sessao(sessao_id):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM sessoes WHERE id = %s", (sessao_id,))
        conn.commit()

def update_sessao(sessao_id, pagamento, valor, status, cobrar, nota_fiscal,
                  conteudo, objetivo, material, atividade_casa, emocao_entrada, emocao_saida, proxima_sessao):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE sessoes 
                SET pagamento = %s,
                    valor = %s,
                    status = %s,
                    cobrar = %s,
                    nota_fiscal = %s,
                    conteudo = %s,
                    objetivo = %s,
                    material = %s,
                    atividade_casa = %s,
                    emocao_entrada = %s,
                    emocao_saida = %s,
                    proxima_sessao = %s
                WHERE id = %s
            """, (
                pagamento, valor, status, cobrar, nota_fiscal,
                conteudo, objetivo, material, atividade_casa,
                emocao_entrada, emocao_saida, proxima_sessao,
                sessao_id
            ))
        conn.commit()

def atualizar_privilegio_usuario(id_usuario, novo_privilegio):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE login SET privilegio = %s WHERE id = %s",
                (int(novo_privilegio), id_usuario)
            )
        conn.commit()

def listar_clientes(psicologo_responsavel):
    with get_mysql_conn() as conn:
       with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM clientes WHERE psicologo_responsavel = %s",(psicologo_responsavel,))
        rows = cursor.fetchall()  # lista de dicionários
       # Define os nomes esperados das colunas
        colunas = ["id","nome","valor_sessao","psicologo_responsavel"]

        if not rows:
            return pd.DataFrame(columns=colunas)
        else:
            return pd.DataFrame(rows, columns=colunas)

def listar_login_privilegios():
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM login")
            rows = cursor.fetchall()  # lista de dicionários
            # Define os nomes esperados das colunas
            colunas = ["id","usuario","senha","funcao","psicologo_responsavel","privilegio"]

            if not rows:
                return pd.DataFrame(columns=colunas)
            else:
                return pd.DataFrame(rows, columns=colunas)

def select_user(usuario, senha):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM login WHERE usuario = %s AND senha = %s", (usuario, senha))
            return cursor.fetchone()
    
def validate_user(id):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM login WHERE id = %s", (id,))
                return cursor.fetchone()

def listar_psicologos():
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM psicologos")
            rows = cursor.fetchall()  # lista de dicionários
            # Define os nomes esperados das colunas
            colunas = ['id', "nome"]

            if not rows:
                return pd.DataFrame(columns=colunas)
            else:
                return pd.DataFrame(rows, columns=colunas)

def sessoes_por_cliente(cliente_id):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM sessoes 
                WHERE cliente_id = %s 
                ORDER BY data DESC, hora DESC
            """, (cliente_id,))
            rows = cursor.fetchall()  # lista de dicionários

            # Lista atualizada com todas as colunas da tabela
            colunas = [
                "id", "cliente_id", "data", "hora", "valor", "status",
                "cobrar", "pagamento", "nota_fiscal", "conteudo", "objetivo",
                "material", "atividade_casa", "emocao_entrada", "emocao_saida",
                "proxima_sessao"
            ]

            if not rows:
                return pd.DataFrame(columns=colunas)
            else:
                return pd.DataFrame(rows, columns=colunas)

def get_proximo_id(tabela, campo='id'):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT MAX({campo}) AS max_id FROM {tabela}")
            resultado = cursor.fetchone()
            return (resultado['max_id'] or 0) + 1

def resumo_financeiro(mes: int, ano: int, psicologo_responsavel):
    with get_mysql_conn() as conn:
        query = """
            SELECT 
                c.nome,
                COUNT(CASE WHEN s.status = 'realizada' THEN 1 END) AS sessoes_feitas,
                COUNT(CASE WHEN s.status = 'falta' THEN 1 END) AS sessoes_faltas,
                SUM(CASE WHEN s.status = 'realizada' AND s.pagamento THEN s.valor ELSE 0 END) AS total_recebido,
                SUM(CASE WHEN (s.status = 'falta' AND s.cobrar) OR 
                          (s.status = 'realizada' AND NOT s.pagamento) THEN s.valor ELSE 0 END) AS total_a_receber
            FROM clientes c
            LEFT JOIN sessoes s ON c.id = s.cliente_id
            WHERE 
                MONTH(s.data) = %s AND
                YEAR(s.data) = %s AND
                c.psicologo_responsavel = %s
            GROUP BY c.nome
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (mes, ano, psicologo_responsavel))
            rows = cursor.fetchall()

            # Define os nomes esperados das colunas
            colunas = ['nome', 'sessoes_feitas', 'sessoes_faltas', 'total_recebido', 'total_a_receber']

            if not rows:
                return pd.DataFrame(columns=colunas)
            else:
                return pd.DataFrame(rows, columns=colunas)
        

# -----------------------
# PDF (inalterado)
# -----------------------

def gerar_pdf(df, cliente_nome):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Relatório de Sessões - {cliente_nome}", ln=True, align='C')
    pdf.ln(10)

    colunas = df.columns.tolist()

    for col in colunas:
        pdf.cell(30, 10, col, border=1)
    pdf.ln()

    for _, row in df.iterrows():
        for col in colunas:
            texto = str(row[col])
            pdf.cell(30, 10, texto[:15], border=1)
        pdf.ln()

    return pdf.output(dest='S').encode('latin1')


criar_tabelas()