# /db/functions.py
import duckdb
import pandas as pd
from fpdf import FPDF
import io

conn = duckdb.connect(database='db/clientes.db')

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
    # Verificar se o cliente já existe
    existente = conn.execute("SELECT COUNT(*) FROM clientes WHERE nome = ?", (nome,)).fetchone()[0]
    if existente:
        raise ValueError("Cliente já cadastrado.")
    result = conn.execute("SELECT MAX(id) FROM clientes").fetchone()
    novo_id = (result[0] or 0) + 1
    conn.execute("INSERT INTO clientes (id, nome, valor_sessao) VALUES (?, ?, ?)", (novo_id, nome, valor_sessao))

def adicionar_sessao(cliente_id, data, hora, valor, status, cobrar):
    # Verificar se sessão com data e hora para o mesmo cliente já existe
    existente = conn.execute("""
        SELECT COUNT(*) FROM sessoes
        WHERE cliente_id = ? AND data = ? AND hora = ?
    """, (int(cliente_id), data, hora)).fetchone()[0]
    if existente:
        raise ValueError("Sessão já registrada para este cliente neste horário.")

    result = conn.execute("SELECT MAX(id) FROM sessoes").fetchone()
    novo_id = (result[0] or 0) + 1
    conn.execute("""
        INSERT INTO sessoes (id, cliente_id, data, hora, valor, status, cobrar)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (novo_id, int(cliente_id), data, hora, valor, status, cobrar))

def excluir_cliente(cliente_id):
    conn.execute("DELETE FROM sessoes WHERE cliente_id = ?", (int(cliente_id),))
    conn.execute("DELETE FROM clientes WHERE id = ?", (int(cliente_id),))

def excluir_sessao(sessao_id):
    conn.execute("DELETE FROM sessoes WHERE id = ?", (int(sessao_id),))

def sessoes_por_cliente(cliente_id):
    return conn.execute("SELECT * FROM sessoes WHERE cliente_id = ?", (int(cliente_id),)).df()

def resumo_financeiro(mes: int, ano: int):
    query = rf"""
    SELECT 
        c.nome,
        COUNT(CASE WHEN s.status = 'realizada' THEN 1 END) AS sessoes_feitas,
        COUNT(CASE WHEN s.status = 'cancelada' THEN 1 END) AS sessoes_canceladas,
        SUM(CASE WHEN s.status = 'realizada' THEN s.valor ELSE 0 END) AS total_recebido,
        SUM(CASE WHEN s.status = 'cancelada' AND s.cobrar THEN s.valor ELSE 0 END) AS total_a_receber
    FROM clientes c
    LEFT JOIN sessoes s 
        ON c.id = s.cliente_id
    WHERE
        strftime('%m', CAST(s.data AS DATE)) = lpad(?, 2, '0') 
        AND strftime('%Y', CAST(s.data AS DATE)) = ?
    GROUP BY c.nome
    """
    return conn.execute(query, (str(mes), str(ano))).df()

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
