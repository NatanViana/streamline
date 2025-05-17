import pymysql
import pandas as pd
from fpdf import FPDF
import os
import duckdb
import streamlit as st

# 🔁 Cria instância DuckDB in-memory
def get_duckdb():
    return duckdb.connect(database=':memory:')
    
# 🔁 Conexão com MySQL (persistência)
def get_mysql_conn():
    return pymysql.connect(
        host=os.getenv("host"),
        user=os.getenv("username"),
        password=os.getenv("password"),
        port=int(os.getenv("port")),
        database=os.getenv("database"),
        cursorclass=pymysql.cursors.DictCursor
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
                    comentario TEXT,
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
                raise ValueError("Psicólogo já cadastrado.")
            cursor.execute("SELECT MAX(id) AS max_id FROM psicologos")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            cursor.execute("INSERT INTO psicologos (id, nome) VALUES (%s, %s)", (novo_id, nome))
        conn.commit()

def adicionar_usuario(usuario, senha, funcao, psicologo_responsavel, privilegio):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM login WHERE usuario = %s", (usuario,))
            if cursor.fetchone()['count']:
                raise ValueError("Usuário já cadastrado.")
            cursor.execute("SELECT MAX(id) AS max_id FROM login")
            novo_id = (cursor.fetchone()['max_id'] or 0) + 1
            cursor.execute("""
                INSERT INTO login (id, usuario, senha, funcao, psicologo_responsavel, privilegio)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (novo_id, usuario, senha, funcao, psicologo_responsavel, privilegio))
        conn.commit()
    if funcao == "Psicóloga":
        adicionar_psicologo(usuario)

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

def adicionar_sessao(cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal, comentario):
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
                INSERT INTO sessoes (id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal, comentario)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (novo_id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal, comentario))
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

def update_sessao(sessao_id, pagamento, valor, status, cobrar, nota_fiscal, comentario):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE sessoes 
                SET pagamento = %s, valor = %s, status = %s, cobrar = %s,
                    nota_fiscal = %s, comentario = %s
                WHERE id = %s
            """, (pagamento, valor, status, cobrar, nota_fiscal, comentario, sessao_id))
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
            cursor.execute("SELECT * FROM sessoes WHERE cliente_id = %s ORDER BY data DESC, hora DESC", (cliente_id,))
            rows = cursor.fetchall()  # lista de dicionários

            # Define os nomes esperados das colunas
            colunas = ["id","cliente_id","data","hora","valor","status","cobrar","pagamento","nota_fiscal","comentario"]

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
                COUNT(CASE WHEN s.status = 'cancelada' THEN 1 END) AS sessoes_canceladas,
                SUM(CASE WHEN s.status = 'realizada' AND s.pagamento THEN s.valor ELSE 0 END) AS total_recebido,
                SUM(CASE WHEN (s.status = 'cancelada' AND s.cobrar) OR 
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
            colunas = ['nome', 'sessoes_feitas', 'sessoes_canceladas', 'total_recebido', 'total_a_receber']

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