# /pages/dashboard.py
import streamlit as st
from db.functions import resumo_financeiro
import pandas as pd
import plotly.express as px
from datetime import datetime
from db.functions import conn, listar_psicologos


def show_dashboard(psicologo_responsavel):
    st.title("📊 Visão Geral do Sistema")
    st.write("Resumo financeiro e de sessões por cliente.")
    psicologos_df = listar_psicologos()
    filtro = psicologos_df[psicologos_df['id'] == psicologo_responsavel]
    if not filtro.empty:
        psicologo = filtro.iloc[0]
        st.write(f"👩🏻‍⚕️ Psicóloga Responsável: {psicologo['nome']}")
    else:
        st.warning("Psicóloga não encontrada.")

    # Filtros por mês e ano
    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox("📅 Mês", list(range(1, 13)), index=datetime.now().month - 1)
        print(mes)
    with col2:
        ano = st.selectbox("📆 Ano", list(range(2023, datetime.now().year + 1)), index = len(list(range(2023, datetime.now().year + 1)))-1)
        print(ano)

    # Exibir resumo financeiro filtrado por mês e ano
    df_resumido = resumo_financeiro(mes, ano, psicologo_responsavel)

    # KPIs
    total_recebido = df_resumido['total_recebido'].sum()
    total_pendente = df_resumido['total_a_receber'].sum()
    total_sessoes = df_resumido['sessoes_feitas'].sum()
    total_canceladas = df_resumido['sessoes_canceladas'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Recebido", f"R$ {total_recebido:,.2f}")
    col2.metric("🧾 Total Pendente", f"R$ {total_pendente:,.2f}")
    col3.metric("📊 Sessões do Mês", f"{total_sessoes} feitas / {total_canceladas} canceladas")

    # Gráfico interativo com Plotly: Recebido vs Pendente
    st.subheader("📈 Financeiro - Recebido vs Pendente")
    dados_grafico = pd.DataFrame({
        'Categoria': ['Recebido', 'Pendente'],
        'Valor': [total_recebido, total_pendente]
    })

    fig = px.bar(
        dados_grafico,
        x="Categoria",
        y="Valor",
        color="Categoria",
        text="Valor",
        title=f"💵 Financeiro - {mes:02}/{ano}"
    )
    fig.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
    fig.update_layout(yaxis_title="Valor em R$", showlegend=False)

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df_resumido, use_container_width=True)