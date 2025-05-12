# /pages/gerenciar_cliente.py
import streamlit as st
import pandas as pd
from fpdf import FPDF
from db.functions import listar_clientes, sessoes_por_cliente, adicionar_sessao, excluir_cliente, excluir_sessao, update_sessao
import io
from datetime import datetime


def gerar_pdf_texto(sessoes, cliente_nome, mes, ano):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Relatório de Sessões - {cliente_nome}      |     {mes}/{ano}", ln=True, align='C')
    pdf.ln(10)

    for i, (_, row) in enumerate(sessoes.iterrows(), start=1):
        hora_formatada = row['hora'][:5] if isinstance(row['hora'], str) else str(row['hora'])[:5]
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(200, 10, txt=f"Sessão {i}", ln=True)
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Data: {row['data'].date()} | Hora: {hora_formatada}", ln=True)
        pdf.cell(200, 10, txt=f"Valor: R$ {row['valor']:.2f}", ln=True)
        pdf.cell(200, 10, txt=f"Status: {row['status']} | Cobrar se cancelada: {'Sim' if row['cobrar'] else 'Não'}", ln=True)
        pdf.cell(200, 10, txt=f"Pendente de Pagamento: {'Sim' if row['pagamento'] else 'Não'}", ln=True)
        pdf.cell(200, 10, txt=f"-----------------------------------------", ln=True)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin1')

def show_gerenciar_cliente(cliente_nome):
    clientes = listar_clientes()
    cliente = clientes[clientes['nome'] == cliente_nome].iloc[0]
    cliente_id = int(cliente['id'])

    st.title(f"🧑 Cliente: {cliente_nome}")

    # Botão para excluir cliente com confirmação
    if st.button("❌ Excluir Cliente"):
        excluir_cliente(cliente_id)
        st.success(f"Cliente {cliente_nome} excluído com sucesso.")
        st.session_state['pagina'] = "🏠 Página Inicial"
        st.rerun()

    st.markdown("### 🗓️ Registrar Nova Sessão")

    with st.form("form_sessao"):
        col1, col2 = st.columns(2)
        with col1:
            data = st.date_input("📅 Data", datetime.today())
            hora = st.time_input("🕒 Hora", datetime.now().replace(second=0, microsecond=0).time())
            hora_str = hora.strftime("%H:%M")
        with col2:
            valor = st.number_input("💵 Valor", min_value=0.0, value=float(cliente['valor_sessao']))
            status = st.selectbox("📌 Status", ["realizada", "cancelada"])
            cobrar = st.checkbox("💸 Cobrar se cancelada", value=False)
            pagamento = st.checkbox("💸 Pago?", value=False) # pode ser a data
        salvar = st.form_submit_button("📂 Salvar Sessão")
        if salvar:
            try:
                adicionar_sessao(cliente_id, str(data), hora_str, valor, status, cobrar, pagamento)
                st.success("Sessão registrada com sucesso!")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown("### 📅 Sessões Registradas")
    sessoes = sessoes_por_cliente(cliente_id)
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

    for _, row in sessoes_filtradas.iterrows():
        with st.expander(f"📍 {row['data'].date()} às {row['hora']} - {row['status']}"):
            st.write(f"💵 Valor: R$ {row['valor']:.2f}")
            st.write(f"💬 Cobrar se cancelada: {'Sim' if row['cobrar'] else 'Não'}")
            pago = bool(row.get('pagamento', False))
            novo_valor = st.checkbox("✅ Pago?", value=pago, key=f"pago_{row['id']}")
            if novo_valor != pago:
                update_sessao(row['id'], novo_valor)
                st.success("Status de pagamento atualizado.")
                st.rerun()
            if st.button(f"🗑️ Excluir sessão {row['id']}", key=f"excluir_{row['id']}"):
                excluir_sessao(row['id'])
                st.success("Sessão excluída com sucesso.")
                st.rerun()

    # Exportar CSV
    csv = sessoes_filtradas.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Exportar CSV", csv, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.csv", mime='text/csv')

    # Exportar PDF (modo descritivo)
    pdf_bytes = gerar_pdf_texto(sessoes_filtradas, cliente_nome, mes, ano)
    st.download_button("📄 Exportar PDF", pdf_bytes, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.pdf", mime='application/pdf')


