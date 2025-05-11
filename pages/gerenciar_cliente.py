# /pages/gerenciar_cliente.py
import streamlit as st
from datetime import datetime
import pandas as pd
from db.functions import listar_clientes, sessoes_por_cliente, adicionar_sessao, gerar_pdf
import io

def show_gerenciar_cliente(client_id):
    clientes = listar_clientes()
    cliente = clientes[clientes['id'] == client_id].iloc[0]
    cliente_nome = cliente['nome']

    st.title(f"📅 Cliente: {cliente_nome}")
    st.markdown("### 🗓️ Registrar Nova Sessão")

    with st.form("form_sessao"):
        col1, col2 = st.columns(2)
        with col1:
            data = st.date_input("📅 Data", datetime.today())
            hora = st.time_input("🕒 Hora", datetime.now().time())
        with col2:
            valor = st.number_input("💵 Valor", min_value=0.0, value=float(cliente['valor_sessao']))
            status = st.selectbox("📌 Status", ["realizada", "cancelada"])
            cobrar = st.checkbox("💸 Cobrar se cancelada", value=False)
        salvar = st.form_submit_button("📂 Salvar Sessão")
        if salvar:
            adicionar_sessao(client_id, str(data), str(hora), valor, status, cobrar)
            st.success("Sessão registrada com sucesso!")

    st.markdown("### 📅 Sessões Registradas")
    sessoes = sessoes_por_cliente(client_id)
    sessoes['data'] = pd.to_datetime(sessoes['data'])

    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox("📅 Mês", list(range(1, 13)), index=datetime.now().month - 1)
    with col2:
        anos_disponiveis = sessoes['data'].dt.year.unique().tolist()
        ano = st.selectbox("📆 Ano", sorted(anos_disponiveis, reverse=True) if anos_disponiveis else [datetime.now().year])

    sessoes_filtradas = sessoes[
        (sessoes['data'].dt.month == mes) &
        (sessoes['data'].dt.year == ano)
    ]

    st.dataframe(sessoes_filtradas, use_container_width=True)

    # Exportar CSV
    csv = sessoes_filtradas.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Exportar CSV", csv, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.csv", mime='text/csv')

    # Exportar PDF
    pdf_bytes = gerar_pdf(sessoes_filtradas, cliente_nome)
    st.download_button("📄 Exportar PDF", pdf_bytes, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.pdf", mime='application/pdf')
