import pymysql
import pandas as pd
import os
import duckdb
import streamlit as st
import ssl
import base64
import tempfile
from functools import lru_cache
from google.cloud import storage
from typing import Optional
from fpdf import FPDF
from datetime import datetime

class PDF(FPDF):
    def header(self):
        self.set_fill_color(14, 43, 58)
        self.rect(0, 0, self.w, self.h, 'F')

        if self.page_no() == 1:
            logo_width = 150
            x_center = (self.w - logo_width) / 2
            y_center = (self.h - logo_width) / 2 - 30
            self.image("assets/logo_neuro_sem_bk.png", x=x_center, y=y_center, w=logo_width)
            self.logo_bottom_y = y_center + logo_width + 10
        else:
            logo_width = 35
            x_centered = (self.w - logo_width) / 2
            self.image("assets/logo_neuro_sem_bk.png", x=x_centered, y=10, w=logo_width)
            self.ln(logo_width + 0)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(240, 240, 240)
        self.cell(0, 10, f"Página {self.page_no() - 1}", align="C")

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
                    dia_agendamento TEXT,
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
                    observacao TEXT,
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

def adicionar_cliente(nome, valor_sessao, psicologo_responsavel, dia_agendamento):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM clientes WHERE nome = %s", (nome,))
            if cursor.fetchone()['count']:
                raise ValueError("Cliente já cadastrado.")
            cursor.execute("SELECT MAX(id) AS max_id FROM clientes")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            cursor.execute("""
                INSERT INTO clientes (id, nome, valor_sessao, psicologo_responsavel, dia_agendamento)
                VALUES (%s, %s, %s, %s, %s)
            """, (novo_id, nome, valor_sessao, psicologo_responsavel, dia_agendamento))
        conn.commit()

def adicionar_sessao(
    cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,
    conteudo, objetivo, material, atividade_casa,
    emocao_entrada, emocao_saida, proxima_sessao, observacao
):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            # Verifica se já existe sessão nesse dia/hora para o cliente
            cursor.execute("""
                SELECT COUNT(*) AS count FROM sessoes
                WHERE cliente_id = %s AND data = %s AND hora = %s
            """, (cliente_id, data, hora))
            if cursor.fetchone()['count']:
                raise ValueError("Sessão já registrada para este cliente neste horário.")
            
            # Gera novo ID
            cursor.execute("SELECT MAX(id) AS max_id FROM sessoes")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            
            # Insere com a nova coluna 'observacao'
            cursor.execute("""
                INSERT INTO sessoes (
                    id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,
                    conteudo, objetivo, material, atividade_casa,
                    emocao_entrada, emocao_saida, proxima_sessao, observacao
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                novo_id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,
                conteudo, objetivo, material, atividade_casa,
                emocao_entrada, emocao_saida, proxima_sessao, observacao
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
                  conteudo, objetivo, material, atividade_casa,
                  emocao_entrada, emocao_saida, proxima_sessao, observacao):
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
                    proxima_sessao = %s,
                    observacao = %s
                WHERE id = %s
            """, (
                pagamento, valor, status, cobrar, nota_fiscal,
                conteudo, objetivo, material, atividade_casa,
                emocao_entrada, emocao_saida, proxima_sessao,
                observacao,
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

def atualizar_nome_cliente(cliente_id: int, novo_nome: str):
    """Atualiza o nome do cliente garantindo que não exista duplicidade global de nome."""
    if not novo_nome or str(novo_nome).strip() == "":
        raise ValueError("Nome inválido.")
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            # impede duplicado de nome (mesma regra usada no adicionar_cliente)
            cursor.execute("SELECT COUNT(*) AS count FROM clientes WHERE nome = %s AND id <> %s", (novo_nome, cliente_id))
            if cursor.fetchone()['count']:
                raise ValueError("Já existe um cliente com esse nome.")
            cursor.execute("UPDATE clientes SET nome = %s WHERE id = %s", (novo_nome, cliente_id))
        conn.commit()

def atualizar_dia_agendamento_cliente(cliente_id: int, novo_dia: str):
    """
    Atualiza o dia de agendamento do cliente.
    Valores permitidos: 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira'.
    """
    DIAS_VALIDOS = {
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Indefinido"
    }

    if novo_dia not in DIAS_VALIDOS:
        raise ValueError("Dia inválido. Use apenas dias úteis (segunda a sexta).")

    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE clientes SET dia_agendamento = %s WHERE id = %s",
                (novo_dia, cliente_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Cliente não encontrado.")
        conn.commit()

def update_sessao_data_hora(sessao_id: int, nova_data: str, nova_hora):
    """
    Altera data e hora da sessão.
    - Garante que não exista outra sessão do MESMO cliente no mesmo dia/hora.
    - 'nova_data' pode ser 'YYYY-MM-DD' (string) ou date.
    - 'nova_hora' pode ser 'HH:MM[:SS]' (string) ou time.
    """
    from datetime import datetime, time

    # normaliza data/hora
    if hasattr(nova_data, "isoformat"):
        data_str = nova_data.strftime("%Y-%m-%d")
    else:
        data_str = str(nova_data)

    if isinstance(nova_hora, time):
        hora_str = nova_hora.strftime("%H:%M:%S")
    else:
        # aceita "HH:MM" ou "HH:MM:SS"
        try:
            hhmm = datetime.strptime(str(nova_hora), "%H:%M")
            hora_str = hhmm.strftime("%H:%M:%S")
        except ValueError:
            hhmmss = datetime.strptime(str(nova_hora), "%H:%M:%S")
            hora_str = hhmmss.strftime("%H:%M:%S")

    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            # descobre o cliente_id da sessão
            cursor.execute("SELECT cliente_id FROM sessoes WHERE id = %s", (sessao_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Sessão não encontrada.")
            cliente_id = row["cliente_id"]

            # impede conflito (outra sessão do mesmo cliente no mesmo dia/hora)
            cursor.execute("""
                SELECT COUNT(*) AS count
                  FROM sessoes
                 WHERE cliente_id = %s
                   AND data = %s
                   AND hora = %s
                   AND id <> %s
            """, (cliente_id, data_str, hora_str, sessao_id))
            if cursor.fetchone()["count"]:
                raise ValueError("Já existe outra sessão deste cliente neste dia/horário.")

            # atualiza
            cursor.execute("""
                UPDATE sessoes
                   SET data = %s, hora = %s
                 WHERE id = %s
            """, (data_str, hora_str, sessao_id))
        conn.commit()

def listar_clientes(psicologo_responsavel):
    with get_mysql_conn() as conn:
       with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM clientes WHERE psicologo_responsavel = %s",(psicologo_responsavel,))
        rows = cursor.fetchall()  # lista de dicionários
       # Define os nomes esperados das colunas
        colunas = ["id","nome","valor_sessao","psicologo_responsavel", "dia_agendamento"]

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
                SELECT
                    id, cliente_id, data, hora, valor, status,
                    cobrar, pagamento, nota_fiscal, conteudo, objetivo,
                    material, atividade_casa, emocao_entrada, emocao_saida,
                    proxima_sessao, observacao
                FROM sessoes 
                WHERE cliente_id = %s 
                ORDER BY data DESC, hora DESC
            """, (cliente_id,))
            rows = cursor.fetchall()

            colunas = [
                "id", "cliente_id", "data", "hora", "valor", "status",
                "cobrar", "pagamento", "nota_fiscal", "conteudo", "objetivo",
                "material", "atividade_casa", "emocao_entrada", "emocao_saida",
                "proxima_sessao", "observacao"
            ]

            if not rows:
                return pd.DataFrame(columns=colunas)
            df = pd.DataFrame(rows, columns=colunas)

            # se sua coluna permitir NULL, garanta string vazia ao invés de NaN (opcional)
            df["observacao"] = df["observacao"].fillna("")
            return df

def get_proximo_id(tabela, campo='id'):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT MAX({campo}) AS max_id FROM {tabela}")
            resultado = cursor.fetchone()
            return (resultado['max_id'] or 0) + 1

def resumo_financeiro(psicologo_responsavel: int, mes: Optional[int] = None, ano: Optional[int] = None) -> pd.DataFrame:
    """
    Retorna o resumo por cliente. Se mes/ano não forem informados, traz TODAS as sessões.
    """
    with get_mysql_conn() as conn:
        # Monta filtros dinâmicos
        filtros = ["c.psicologo_responsavel = %s"]
        params = [psicologo_responsavel]

        if ano is not None:
            filtros.append("YEAR(s.data) = %s")
            params.append(ano)
        if mes is not None:
            filtros.append("MONTH(s.data) = %s")
            params.append(mes)

        where_sql = " AND ".join(filtros)

        query = f"""
            SELECT 
                c.nome,
                COUNT(CASE WHEN s.status = 'realizada' THEN 1 END) AS sessoes_feitas,
                COUNT(CASE WHEN s.status = 'falta' THEN 1 END) AS sessoes_faltas,
                COALESCE(SUM(CASE WHEN s.status = 'realizada' AND s.pagamento THEN s.valor ELSE 0 END), 0) AS total_recebido,
                COALESCE(SUM(CASE 
                    WHEN (s.status = 'falta' AND s.cobrar = 1) OR 
                         (s.status = 'realizada' AND (s.pagamento = 0 OR s.pagamento IS NULL)) 
                    THEN s.valor ELSE 0 END), 0) AS total_a_receber
            FROM clientes c
            LEFT JOIN sessoes s ON c.id = s.cliente_id
            WHERE {where_sql}
            GROUP BY c.nome
            ORDER BY c.nome
        """
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        colunas = ['nome', 'sessoes_feitas', 'sessoes_faltas', 'total_recebido', 'total_a_receber']
        return pd.DataFrame(rows, columns=colunas) if rows else pd.DataFrame(columns=colunas)
    
def resumo_pendencias(
    psicologo_responsavel,
    dt_inicio,
    dt_fim,
) -> pd.DataFrame:
    """
    Pendências = sessões:
      - status = 'realizada' AND pagamento = 0/NULL
      - status = 'falta' AND pagamento = 0/NULL AND cobrar = 1

    Filtra sempre pelo período [dt_inicio, dt_fim].

    Retorna por cliente: contagens e valor total pendente.
    """
    with get_mysql_conn() as conn:
        query = """
            SELECT
                c.id AS cliente_id,
                c.nome,
                COUNT(CASE WHEN s.status='realizada' AND (s.pagamento = 0 OR s.pagamento IS NULL) THEN 1 END) AS realizadas_pendentes,
                COUNT(CASE WHEN s.status='falta' AND (s.pagamento = 0 OR s.pagamento IS NULL) AND s.cobrar = 1 THEN 1 END) AS faltas_cobraveis_pendentes,
                COALESCE(SUM(CASE 
                    WHEN s.status='realizada' AND (s.pagamento = 0 OR s.pagamento IS NULL) THEN s.valor
                    WHEN s.status='falta' AND (s.pagamento = 0 OR s.pagamento IS NULL) AND s.cobrar = 1 THEN s.valor
                    ELSE 0 END), 0) AS valor_pendente
            FROM clientes c
            JOIN sessoes s ON c.id = s.cliente_id
            WHERE c.psicologo_responsavel = %s
              AND DATE(s.data) BETWEEN %s AND %s
            GROUP BY c.id, c.nome
            HAVING (realizadas_pendentes + faltas_cobraveis_pendentes) > 0
            ORDER BY valor_pendente DESC, c.nome
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (psicologo_responsavel, dt_inicio, dt_fim))
            rows = cursor.fetchall()

        colunas = ['cliente_id','nome', 'realizadas_pendentes', 'faltas_cobraveis_pendentes', 'valor_pendente']
        return pd.DataFrame(rows, columns=colunas) if rows else pd.DataFrame(columns=colunas)

# -----------------------
# PDF (inalterado)
# -----------------------
def gerar_pdf_texto(sessoes, cliente_nome, mes, ano, finalidade):
    MESES_PT = {
        "1": "Janeiro", "2": "Fevereiro", "3": "Março", "4": "Abril",
        "5": "Maio", "6": "Junho", "7": "Julho", "8": "Agosto",
        "9": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
    }

    mes_nome = MESES_PT.get(str(int(mes)), "Mês Inválido")
    pdf = PDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Capa
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 22)
    pdf.set_y(pdf.h - 70)
    pdf.cell(0, 10, f"Relatório de Sessões - {cliente_nome}", ln=True, align="C")

    pdf.set_y(pdf.h - 40)
    pdf.set_font("Arial", "", 16)
    pdf.cell(0, 10, f"{mes_nome} de {ano}", ln=True, align="C")

    # Página de sessões
    pdf.add_page()

    for i, (_, row) in enumerate(sessoes.iterrows(), start=1):
        hora_formatada = row['hora'][:5] if isinstance(row['hora'], str) else str(row['hora'])[:5]

        # Título centralizado
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(247, 215, 145)
        pdf.cell(0, 10, f"Sessão {i}", ln=True, align="C")

        # Tabela centralizada
        pdf.set_fill_color(38, 64, 78)
        pdf.set_draw_color(60, 90, 110)
        pdf.set_text_color(255, 255, 255)

        campos = [
            ("Data", str(row['data'].date())),
            ("Hora", hora_formatada),
            ("Valor", f"R$ {row['valor']:.2f}"),
            ("Status", row['status'].capitalize()),
            ("Pendente", "Não" if row['pagamento'] else "Sim"),
            ("Nota Fiscal", row.get("nota_fiscal") or "NF- N/D"),
            ("Observação", row.get("observacao") or "N/A")
        ]
        if finalidade != 'Cliente':
            campos.insert(4, ("Cobrar Cancelado", "Sim" if row['cobrar'] else "Não"))

        col_width = 70
        x_margin = (pdf.w - 2 * col_width) / 2
        cell_height = 7

        for label, valor in campos:
            pdf.set_x(x_margin)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(col_width, cell_height, f"{label}:", border=1, fill=True)
            pdf.set_font("Arial", "", 9)
            pdf.cell(col_width, cell_height, str(valor), border=1, ln=True, fill=True, align="C")

        # Diário
        if finalidade != 'Cliente':
            pdf.ln(2)
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 8, "Diário de Sessão", ln=True, align="C")

            emocoes = {
                1: "Triste",
                2: "Chateado",
                3: "Neutro",
                4: "Contente",
                5: "Feliz"
            }

            entrada_val = row.get("emocao_entrada")
            saida_val = row.get("emocao_saida")

            entrada_desc = emocoes.get(int(entrada_val), "N/D") if pd.notnull(entrada_val) else "N/D"
            saida_desc = emocoes.get(int(saida_val), "N/D") if pd.notnull(saida_val) else "N/D"

            blocos = [
                ("Conteúdo", row.get("conteudo") or "Não registrado"),
                ("Objetivo", row.get("objetivo") or "Não registrado"),
                ("Material", row.get("material") or "Não registrado"),
                ("Ativ. Casa", row.get("atividade_casa") or "Não registrada"),
                ("Emoção Entrada", entrada_desc),
                ("Emoção Saída", saida_desc),
                ("Próxima Sessão", row.get("proxima_sessao") or "Não registrada")
            ]

            # Tabela centralizada
            pdf.set_fill_color(38, 64, 78)
            pdf.set_draw_color(60, 90, 110)
            pdf.set_text_color(255, 255, 255)

            for label, valor in blocos:
                pdf.set_x(x_margin)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(col_width, 6, f"{label}:", border=1, fill=True)
                pdf.set_font("Arial", "", 9)
                pdf.multi_cell(col_width, 6, str(valor), border=1, fill=True, align="C")

        pdf.ln(8)

    # Página final com estatísticas
    pdf.add_page()
    
    # Garantir tipos
    sessoes["status"] = sessoes["status"].astype(str).str.strip()
    sessoes["pagamento"] = sessoes["pagamento"].astype(int)
    sessoes["cobrar"] = sessoes["cobrar"].astype(int)
    sessoes["valor"] = pd.to_numeric(sessoes["valor"], errors="coerce").fillna(0)

    # Filtragem correta 
    sessoes_feitas = sessoes[sessoes["status"].str.lower() == "realizada"] 
    sessoes_nao_feitas = sessoes[sessoes["status"].str.lower() == "falta"]

    # Máscaras
    feitas = sessoes["status"].str.lower() == "realizada"
    nao_feitas_cobrar = (sessoes["status"].str.lower() == "falta") & (sessoes["cobrar"] == 1)

    # 1) valor_total = (feitas) OU (não feitas com cobrar=1)
    valor_total = sessoes.loc[feitas | nao_feitas_cobrar, "valor"].sum()

    # 2) valor_pago = todas as sessões com pagamento=1
    valor_pago = sessoes.loc[sessoes["pagamento"] == 1, "valor"].sum()

    # 3) valor_pendente = (feitas OU não feitas com cobrar=1) e pagamento=0
    valor_pendente = sessoes.loc[(feitas | nao_feitas_cobrar) & (sessoes["pagamento"] == 0), "valor"].sum()

    # Título
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(247, 215, 145)
    pdf.cell(0, 10, "Estatísticas do Mês", ln=True, align="C")
    pdf.ln(10)

    # Texto
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, f"Número de sessões feitas: {len(sessoes_feitas)}", ln=True, align="C")
    pdf.cell(0, 8, f"Número de faltas: {len(sessoes_nao_feitas)}", ln=True, align="C")
    pdf.cell(0, 8, f"Valor total: R$ {valor_total:.2f}", ln=True, align="C")
    pdf.cell(0, 8, f"Valor pago: R$ {valor_pago:.2f}", ln=True, align="C")
    pdf.cell(0, 8, f"Valor pendente: R$ {valor_pendente:.2f}", ln=True, align="C")

    return pdf.output(dest="S").encode("latin1")


def gerar_pdf_pendencias(sessoes, cliente_nome):
    """
    Gera um PDF de pendências financeiras do cliente ao longo de TODO o histórico,
    ignorando mês/ano/finalidade.

    Parâmetros:
        sessoes (pd.DataFrame): deve conter colunas como
            - data (datetime ou string parseável)
            - hora (string "HH:MM" ou similar)
            - valor (numérico)
            - status (ex.: "realizada", "falta")
            - pagamento (0 ou 1)
            - cobrar (0 ou 1)  # se deve cobrar falta
            - nota_fiscal (opcional)
            - observacao (opcional)
        cliente_nome (str): nome do cliente

    Retorno:
        bytes: conteúdo do PDF (latin1) para download/uso.
    """

    # --- Sanitização e tipos ---
    df = sessoes.copy()

    # Datas e hora
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
    else:
        df["data"] = pd.NaT

    # Tipos e normalizações
    df["status"] = df.get("status", "").astype(str).str.strip()
    df["pagamento"] = pd.to_numeric(df.get("pagamento", 0), errors="coerce").fillna(0).astype(int)
    df["cobrar"] = pd.to_numeric(df.get("cobrar", 0), errors="coerce").fillna(0).astype(int)
    df["valor"] = pd.to_numeric(df.get("valor", 0), errors="coerce").fillna(0.0)

    # --- Regra de pendência ---
    feitas = df["status"].str.lower() == "realizada"
    faltas_cobrar = (df["status"].str.lower() == "falta") & (df["cobrar"] == 1)
    pendente_mask = (feitas | faltas_cobrar) & (df["pagamento"] == 0)

    pendentes = df.loc[pendente_mask].copy()

    # Ordena por data (asc), depois hora se existir
    if "hora" in pendentes.columns:
        pendentes["hora_str"] = pendentes["hora"].astype(str).str[:5]
    else:
        pendentes["hora_str"] = ""

    pendentes = pendentes.sort_values(["data", "hora_str"], na_position="last")

    # --- Montagem do PDF ---
    pdf = PDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # Capa
    pdf.add_page()
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 22)
    pdf.set_y(pdf.h - 80)
    pdf.cell(0, 10, f"Pendências Financeiras - {cliente_nome}", ln=True, align="C")

    pdf.set_y(pdf.h - 50)
    pdf.set_font("Arial", "", 14)
    hoje_str = datetime.now().strftime("%d/%m/%Y")
    pdf.cell(0, 10, f"Consolidado até {hoje_str}", ln=True, align="C")

    # Página de pendências
    pdf.add_page()

    if pendentes.empty:
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(247, 215, 145)
        pdf.cell(0, 10, "Não há pendências financeiras.", ln=True, align="C")
        pdf.ln(8)
    else:
        # Para cada pendência, renderiza um bloco tipo "tabela" centralizada
        for i, (_, row) in enumerate(pendentes.iterrows(), start=1):
            data_str = ""
            if pd.notnull(row["data"]):
                data_str = row["data"].date().isoformat()

            hora_formatada = row.get("hora_str") or ""
            valor_str = f"R$ {float(row['valor']):.2f}"
            status_fmt = str(row.get("status", "")).capitalize()
            nf = row.get("nota_fiscal") or "NF- N/D"
            obs = row.get("observacao") or "N/A"
            cobrar_txt = "Sim" if int(row.get("cobrar", 0)) == 1 else "Não"

            # Título
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(247, 215, 145)
            pdf.cell(0, 10, f"Pendência {i}", ln=True, align="C")

            # Tabela
            pdf.set_fill_color(38, 64, 78)
            pdf.set_draw_color(60, 90, 110)
            pdf.set_text_color(255, 255, 255)

            campos = [
                ("Data", data_str or "N/D"),
                ("Hora", hora_formatada or "N/D"),
                ("Valor", valor_str),
                ("Status", status_fmt or "N/D"),
                ("Cobrar Cancelado", cobrar_txt),
                ("Nota Fiscal", nf),
                ("Observação", obs),
            ]

            col_width = 70
            x_margin = (pdf.w - 2 * col_width) / 2
            cell_h = 7

            for label, valor in campos:
                pdf.set_x(x_margin)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(col_width, cell_h, f"{label}:", border=1, fill=True)
                pdf.set_font("Arial", "", 9)
                # multi_cell para campos que podem ser longos (NF/Observação)
                if label in ("Observação",):
                    pdf.multi_cell(col_width, cell_h, str(valor), border=1, fill=True, align="C")
                else:
                    pdf.cell(col_width, cell_h, str(valor), border=1, ln=True, fill=True, align="C")

            pdf.ln(8)

    # Página final com estatísticas gerais de pendência
    pdf.add_page()

    qtd_pendencias = int(len(pendentes))
    valor_pendente_total = float(pendentes["valor"].sum())

    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(247, 215, 145)
    pdf.cell(0, 10, "Resumo de Pendências", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, f"Quantidade de pendências: {qtd_pendencias}", ln=True, align="C")
    pdf.cell(0, 8, f"Valor total pendente: R$ {valor_pendente_total:.2f}", ln=True, align="C")

    # (Opcional) Quebra por mês/ano para dar visão temporal
    if not pendentes.empty and pd.notnull(pendentes["data"]).any():
        pdf.ln(8)
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(247, 215, 145)
        pdf.cell(0, 8, "Pendências por Mês/Ano", ln=True, align="C")

        by_month = (
            pendentes.assign(ym=pendentes["data"].dt.to_period("M").astype(str))
            .groupby("ym")["valor"].sum()
            .reset_index()
            .sort_values("ym")
        )

        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(38, 64, 78)
        pdf.set_draw_color(60, 90, 110)
        pdf.set_font("Arial", "B", 10)

        # tabela centralizada
        col_w = 80
        x_margin = (pdf.w - 2 * col_w) / 2
        row_h = 7

        # cabeçalho
        pdf.set_x(x_margin)
        pdf.cell(col_w, row_h, "Mês/Ano", border=1, fill=True, align="C")
        pdf.cell(col_w, row_h, "Valor Pendente (R$)", border=1, fill=True, ln=True, align="C")

        pdf.set_font("Arial", "", 10)
        for _, r in by_month.iterrows():
            pdf.set_x(x_margin)
            pdf.cell(col_w, row_h, str(r["ym"]), border=1, fill=True, align="C")
            pdf.cell(col_w, row_h, f"{float(r['valor']):.2f}", border=1, fill=True, ln=True, align="C")

    return pdf.output(dest="S").encode("latin1")


criar_tabelas()