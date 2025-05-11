# /db/functions.py
import duckdb
import pandas as pd
from fpdf import FPDF
import io

conn = duckdb.connect(database='../clientes.db')

# Criação das tabelas (manual ID)
conn.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id BIGINT PRIMARY KEY,
    nome TEXT,
    valor_sessao DOUBLE
);
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS sessoes (
    id BIGINT PRIMARY KEY,
    cliente_id BIGINT,
    data TEXT,
    hora TEXT,
    valor DOUBLE,
    status TEXT,
    cobrar BOOLEAN
);
""")

def listar_clientes():
    return conn.execute("SELECT * FROM clientes").df()

def adicionar_cliente(nome, valor_sessao):
    result = conn.execute("SELECT MAX(id) FROM clientes").fetchone()
    novo_id = (result[0] or 0) + 1
    conn.execute("INSERT INTO clientes (id, nome, valor_sessao) VALUES (?, ?, ?)", (novo_id, nome, valor_sessao))
    return novo_id

def adicionar_sessao(cliente_id, data, hora, valor, status, cobrar):
    result = conn.execute("SELECT MAX(id) FROM sessoes").fetchone()
    novo_id = (result[0] or 0) + 1
    conn.execute("""
        INSERT INTO sessoes (id, cliente_id, data, hora, valor, status, cobrar)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (novo_id, int(cliente_id), data, hora, valor, status, cobrar))

def sessoes_por_cliente(cliente_id):
    return conn.execute("SELECT * FROM sessoes WHERE cliente_id = ?", (int(cliente_id),)).df()

def resumo_financeiro():
    query = """
        SELECT c.nome,
               COUNT(CASE WHEN s.status = 'realizada' THEN 1 END) AS sessoes_feitas,
               COUNT(CASE WHEN s.status = 'cancelada' THEN 1 END) AS sessoes_canceladas,
               SUM(CASE WHEN s.status = 'realizada' THEN s.valor ELSE 0 END) AS total_recebido,
               SUM(CASE WHEN s.status = 'cancelada' AND s.cobrar THEN s.valor ELSE 0 END) AS total_a_receber
        FROM clientes c
        LEFT JOIN sessoes s ON c.id = s.cliente_id
        GROUP BY c.nome
    """
    return conn.execute(query).df()

def gerar_pdf(df, cliente_nome):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Relatório de Sessões - {cliente_nome}", ln=True, align='C')
    pdf.ln(10)

    colunas = df.columns.tolist()
    col_widths = [30] * len(colunas)

    for col in colunas:
        pdf.cell(30, 10, col, border=1)
    pdf.ln()

    for _, row in df.iterrows():
        for col in colunas:
            texto = str(row[col])
            pdf.cell(30, 10, texto[:15], border=1)
        pdf.ln()

    # ✅ Retorna PDF como bytes diretamente
    return pdf.output(dest='S').encode('latin1')
