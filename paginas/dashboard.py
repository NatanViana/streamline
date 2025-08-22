# /pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from db.functions import resumo_financeiro, resumo_pendencias, listar_psicologos, gerar_pdf_pendencias, sessoes_por_cliente

def _kpis_e_grafico(df_resumido: pd.DataFrame, titulo: str):
    total_recebido = float(df_resumido['total_recebido'].sum()) if not df_resumido.empty else 0.0
    total_pendente = float(df_resumido['total_a_receber'].sum()) if not df_resumido.empty else 0.0
    total_sessoes = int(df_resumido['sessoes_feitas'].sum()) if not df_resumido.empty else 0
    total_faltas = int(df_resumido['sessoes_faltas'].sum()) if not df_resumido.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Recebido", f"R$ {total_recebido:,.2f}")
    col2.metric("🧾 Total Pendente", f"R$ {total_pendente:,.2f}")
    col3.metric("📊 Sessões", f"{total_sessoes} Feitas / {total_faltas} Faltas")

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
        title=titulo
    )
    fig.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
    fig.update_layout(yaxis_title="Valor em R$", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df_resumido, use_container_width=True)

def show_dashboard(psicologo_responsavel: int):
    st.title("📊 Visão Geral do Sistema")
    st.write("Resumo financeiro e de sessões por cliente.")

    psicologos_df = listar_psicologos()
    filtro = psicologos_df[psicologos_df['id'] == psicologo_responsavel]
    if not filtro.empty:
        psicologo = filtro.iloc[0]
        st.write(f"👩🏻‍⚕️ Psicóloga Responsável: {psicologo['nome']}")
    else:
        st.warning("Psicóloga não encontrada.")

    # Prefixo estável para keys (evita colisão em múltiplos usuários/abas)
    key_prefix = f"dash_{psicologo_responsavel}_"

    st.markdown(
        """
        <style>
        .stTabs [data-baseweb="tab-list"] {
            display: flex;
            justify-content: space-between;
        }
        .stTabs [data-baseweb="tab"] {
            flex: 1;
            max-width: 25% !important;   /* força 25% pra cada aba */
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Tabs: Global (todas as sessões), Anual, Mensal, Pendências
    tab_global, tab_anual, tab_mensal, tab_pend = st.tabs(["🌍 Global", "📅 Anual", "🗓️ Mensal", "❗ Pendências"])

    with tab_global:
        st.caption("Todas as sessões (sem filtro de mês/ano).")
        df_resumido = resumo_financeiro(psicologo_responsavel=psicologo_responsavel, mes=None, ano=None)
        _kpis_e_grafico(df_resumido, titulo="💵 Financeiro - Global")

    with tab_anual:
        col1 = st.columns(1)[0]
        anos = list(range(2023, datetime.now().year + 1))
        ano = col1.selectbox(
            "📆 Ano",
            anos,
            index=len(anos) - 1,
            key=key_prefix + "anual_ano_select",
        )
        df_resumido = resumo_financeiro(psicologo_responsavel=psicologo_responsavel, ano=ano, mes=None)
        _kpis_e_grafico(df_resumido, titulo=f"💵 Financeiro - {ano}")

    with tab_mensal:
        col1, col2 = st.columns(2)
        mes = col1.selectbox(
            "📅 Mês",
            list(range(1, 13)),
            index=datetime.now().month - 1,
            key=key_prefix + "mensal_mes_select",
        )
        anos = list(range(2023, datetime.now().year + 1))
        ano = col2.selectbox(
            "📆 Ano",
            anos,
            index=len(anos) - 1,
            key=key_prefix + "mensal_ano_select",
        )
        df_resumido = resumo_financeiro(psicologo_responsavel=psicologo_responsavel, mes=mes, ano=ano)
        _kpis_e_grafico(df_resumido, titulo=f"💵 Financeiro - {mes:02}/{ano}")

    with tab_pend:
        st.caption("Clientes com valores pendentes (sessões realizadas não pagas ou faltas cobradas não pagas).")

        # 🔎 Filtro por período (data início e fim)
        col1, col2 = st.columns(2)
        hoje = datetime.now().date()
        padrao_inicio = hoje.replace(day=1)  # 1º dia do mês atual
        dt_inicio = col1.date_input("Data início", value=padrao_inicio, key=key_prefix + "pend_dt_inicio")
        dt_fim = col2.date_input("Data fim", value=hoje, key=key_prefix + "pend_dt_fim")

        # Garante ordem válida
        if dt_fim < dt_inicio:
            st.warning("⚠️ A data fim é anterior à data início. Ajuste o período.")
            st.stop()

        # Título do período
        titulo = f"Pendências - {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"

        # 🧮 Chamada ao backend (sempre por período)
        df_pend = resumo_pendencias(psicologo_responsavel, dt_inicio=dt_inicio, dt_fim=dt_fim)

        # KPIs de pendências
        valor_total_pendente = float(df_pend['valor_pendente'].sum()) if not df_pend.empty else 0.0
        qtd_total_itens = int(
            df_pend['realizadas_pendentes'].fillna(0).sum() +
            df_pend['faltas_cobraveis_pendentes'].fillna(0).sum()
        ) if not df_pend.empty else 0

        c1, c2 = st.columns(2)
        c1.metric("🔔 Valor Total Pendente", f"R$ {valor_total_pendente:,.2f}")
        c2.metric("📌 Itens Pendentes", f"{qtd_total_itens}")

        # Tabela
        st.subheader(titulo)
        st.dataframe(df_pend, use_container_width=True)

        # Gráfico de barras por cliente
        if not df_pend.empty:
            fig = px.bar(
                df_pend.sort_values('valor_pendente', ascending=False),
                x='nome', y='valor_pendente', text='valor_pendente',
                title=titulo
            )
            fig.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
            fig.update_layout(yaxis_title="Valor em R$", xaxis_title="Cliente", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

       # --- Exportar PDF de pendências por cliente (histórico completo) ---
        st.markdown("### ⚠️ Exportar relatório de pendências de sessões (global)")

        if not df_pend.empty:
            # opções (id + nome) a partir do df_pend
            opts = (
                df_pend[['cliente_id', 'nome']]
                .dropna()
                .drop_duplicates()
                .sort_values('nome')
            )
            opcoes = [{'id': int(r.cliente_id), 'nome': r.nome} for _, r in opts.iterrows()]

            selecionado = st.selectbox(
                "Selecione o cliente",
                options=opcoes,
                format_func=lambda o: o['nome'],
                key=key_prefix + "pend_pdf_cliente",
            )

            if st.button("📄 Gerar PDF de Pendências", key=key_prefix + "pend_pdf_btn"):
                try:
                    sessoes = sessoes_por_cliente(selecionado['id'])
                    cliente_nome = selecionado['nome']

                    pdf_bytes_pend = gerar_pdf_pendencias(sessoes, cliente_nome)
                    nome_arquivo_pend = f"pendencias_{''.join(ch if ch.isalnum() else '_' for ch in cliente_nome)}.pdf"

                    st.download_button(
                        "⬇️ Exportar Pendências PDF",
                        data=pdf_bytes_pend,
                        file_name=nome_arquivo_pend,
                        mime="application/pdf",
                        key=key_prefix + "btn_export_pend",
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar o PDF: {e}")
        else:
            st.info("Não há clientes com pendências para exportação.")