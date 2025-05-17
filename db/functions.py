# /db/functions.py
import duckdb
import pandas as pd
from fpdf import FPDF
import io

conn = duckdb.connect(database='db/clientes.db')

# Criação das tabelas (manual ID)

conn.execute("""
CREATE TABLE IF NOT EXISTS psicologos (
    id BIGINT PRIMARY KEY,
    nome TEXT
);
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS login (
    id BIGINT PRIMARY KEY,
    usuario TEXT,
    senha TEXT,
    funcao TEXT,
    psicologo_responsavel BIGINT,
    privilegio BOOLEAN
);
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id BIGINT PRIMARY KEY,
    nome TEXT,
    valor_sessao DOUBLE,
    psicologo_responsavel BIGINT       
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
    cobrar BOOLEAN,
    pagamento BOOLEAN,
    nota_fiscal TEXT,
    comentario TEXT        
);
""")

def adicionar_psicologo(nome):
    # Verificar se o psicologo já existe
    existente = conn.execute("SELECT COUNT(*) FROM psicologos WHERE nome = ?", (nome,)).fetchone()[0]
    if existente:
        raise ValueError("Psicologo já cadastrado.")
    
    # Gerar novo id incremental
    result = conn.execute("SELECT MAX(id) FROM psicologos").fetchone()
    novo_id = (result[0] or 0) + 1

    # Inserir novo psicologo
    conn.execute("INSERT INTO psicologos (id, nome) VALUES (?, ?)", (novo_id, nome))
    conn.commit()

def adicionar_usuario(usuario, senha, funcao, psicologo_responsavel, privilegio):
    # Verificar se o usuário já existe
    existente = conn.execute("SELECT COUNT(*) FROM login WHERE usuario = ?", (usuario,)).fetchone()[0]
    if existente:
        raise ValueError("Usuário já cadastrado.")
    
    # Gerar novo id incremental
    result = conn.execute("SELECT MAX(id) FROM login").fetchone()
    novo_id = (result[0] or 0) + 1

    # Inserir novo usuário
    conn.execute("INSERT INTO login (id, usuario, senha, funcao, psicologo_responsavel, privilegio) VALUES (?, ?, ?, ?, ?, ?)", (novo_id, usuario, senha, funcao, psicologo_responsavel, privilegio))
    conn.commit()

    if funcao == "Psicóloga":
        adicionar_psicologo(usuario)

def listar_clientes(psicologo_responsavel):
    return conn.execute("SELECT * FROM clientes WHERE psicologo_responsavel = ? ",(psicologo_responsavel,)).df()

def listar_psicologos():
    return conn.execute("SELECT * FROM psicologos").df()

def adicionar_cliente(nome, valor_sessao, psicologo_responsavel):
    # Verificar se o cliente já existe
    existente = conn.execute("SELECT COUNT(*) FROM clientes WHERE nome = ?", (nome,)).fetchone()[0]
    if existente:
        raise ValueError("Cliente já cadastrado.")
    result = conn.execute("SELECT MAX(id) FROM clientes").fetchone()
    novo_id = (result[0] or 0) + 1
    conn.execute("INSERT INTO clientes (id, nome, valor_sessao, psicologo_responsavel) VALUES (?, ?, ?, ?)", (novo_id, nome, valor_sessao, psicologo_responsavel))
    conn.commit()

def adicionar_sessao(cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal,comentario):
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
        INSERT INTO sessoes (id, cliente_id, data, hora, valor, status, cobrar, pagamento, nota_fiscal, comentario)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (novo_id, int(cliente_id), data, hora, valor, status, cobrar, pagamento, nota_fiscal, comentario))
    conn.commit()

def excluir_cliente(cliente_id):
    conn.execute("DELETE FROM sessoes WHERE cliente_id = ?", (int(cliente_id),))
    conn.execute("DELETE FROM clientes WHERE id = ?", (int(cliente_id),))
    conn.commit()

def excluir_sessao(sessao_id):
    conn.execute("DELETE FROM sessoes WHERE id = ?", (int(sessao_id),))
    conn.commit()

def update_sessao(sessao_id, pagamento, valor, status, cobrar, nota_fiscal, comentario):
    sql = """
        UPDATE sessoes 
        SET pagamento = ?, 
            valor = ?, 
            status = ?, 
            cobrar = ?, 
            nota_fiscal = ?, 
            comentario = ?
        WHERE id = ?
    """
    conn.execute(sql, (pagamento, valor, status, cobrar, nota_fiscal, comentario, int(sessao_id)))
    conn.commit()

def sessoes_por_cliente(cliente_id):
    return conn.execute("SELECT * FROM sessoes WHERE cliente_id = ?", (int(cliente_id),)).df()

def resumo_financeiro(mes: int, ano: int, psicologo_responsavel):
    query = rf"""
    SELECT 
        c.nome,
        COUNT(CASE WHEN s.status = 'realizada' THEN 1 END) AS sessoes_feitas,
        COUNT(CASE WHEN s.status = 'cancelada' THEN 1 END) AS sessoes_canceladas,
        SUM(CASE WHEN s.status = 'realizada' AND s.pagamento THEN s.valor ELSE 0 END) AS total_recebido,
        SUM(CASE WHEN (s.status = 'cancelada' AND s.cobrar) OR (s.status = 'realizada' AND NOT s.pagamento) THEN s.valor ELSE 0 END) AS total_a_receber
    FROM clientes c
    LEFT JOIN sessoes s 
        ON c.id = s.cliente_id
    WHERE
        strftime('%m', CAST(s.data AS DATE)) = lpad(?, 2, '0') 
        AND strftime('%Y', CAST(s.data AS DATE)) = ?
        AND psicologo_responsavel = ?
    GROUP BY c.nome
    """
    return conn.execute(query, (str(mes), str(ano), psicologo_responsavel)).df()

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
