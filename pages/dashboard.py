# /pages/dashboard.py
import streamlit as st
from db.functions import resumo_financeiro
import pandas as pd
import plotly.express as px
from datetime import datetime


def show_dashboard():
    st.title("📊 Visão Geral do Sistema")
    st.write("Resumo financeiro e de sessões por cliente.")

    # Filtros por mês e ano
    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox("📅 Mês", list(range(1, 13)), index=datetime.now().month - 1)
    with col2:
        ano = st.selectbox("📆 Ano", list(range(2023, datetime.now().year + 1)), index=1)

    # Obter dados
    df = resumo_financeiro()

    # KPIs
    total_recebido = df['total_recebido'].sum()
    total_pendente = df['total_a_receber'].sum()
    total_sessoes = df['sessoes_feitas'].sum()
    total_canceladas = df['sessoes_canceladas'].sum()

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

    st.dataframe(df, use_container_width=True)