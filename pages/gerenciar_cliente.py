# /pages/gerenciar_cliente.py
import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from db.functions import listar_clientes, sessoes_por_cliente, adicionar_sessao, excluir_cliente, excluir_sessao, update_sessao, listar_psicologos
import time

def gerar_horarios():
        horarios = []
        for h in range(0, 24):
            for m in [0, 30]:
                horarios.append(f"{h:02d}:{m:02d}")
        return horarios

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
        
        # Adicionando Nota Fiscal
        nota_fiscal = row.get('nota_fiscal', 'NF- N/D')
        pdf.cell(200, 10, txt=f"Nota Fiscal: {nota_fiscal}", ln=True)

        # Adicionando Comentário
        comentario = row.get('comentario', 'Sem comentário')
        pdf.multi_cell(0, 10, txt=f"Comentário: {comentario}")
        
        pdf.cell(200, 10, txt=f"-----------------------------------------", ln=True)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin1')

def show_gerenciar_cliente(cliente_nome, psicologo_responsavel):
    clientes = listar_clientes(psicologo_responsavel)
    cliente = clientes[clientes['nome'] == cliente_nome].iloc[0]
    cliente_id = int(cliente['id'])
    psicologos_df = listar_psicologos()
    filtro = psicologos_df[psicologos_df['id'] == psicologo_responsavel]
    if not filtro.empty:
        psicologo = filtro.iloc[0]
    else:
        st.warning("Psicóloga não encontrada.")

    if not clientes.empty:
        st.title(f"🧑 Cliente: {cliente_nome}")
        st.write(f"👩🏻‍⚕️ Psicóloga Responsavel: {psicologo['nome']}")
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
                horarios = gerar_horarios()
                hora = st.selectbox("🕒 Hora", horarios)
            with col2:
                valor = st.number_input("💵 Valor", min_value=0.0, value=float(cliente['valor_sessao']))
                status = st.selectbox("📌 Status", ["realizada", "cancelada"])
                cobrar = st.checkbox("💸 Cobrar se cancelada", value=False)
                pagamento = st.checkbox("💸 Pago", value=False)
            nota_fiscal = st.text_input("📑 Nota Fiscal (Comece com NF-)", "NF-")
            comentario = st.text_area("🗒️ Comentário da Sessão", "")

            salvar = st.form_submit_button("📂 Salvar Sessão")
            if salvar:
                if not nota_fiscal.startswith("NF-"):
                    st.error("Nota Fiscal deve iniciar com 'NF-'")
                else:
                    try:
                        adicionar_sessao(
                            cliente_id,
                            str(data),
                            str(hora),
                            valor,
                            status,
                            cobrar,
                            pagamento,
                            nota_fiscal,
                            comentario
                        )
                        st.success(f"Sessão em {data} às {hora} registrada com sucesso!")
                        time.sleep(0.5)
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
                novo_valor = st.number_input(f"💵 Valor", min_value=0.0, value=row['valor'], key=f"valor_{row['id']}")
                novo_status = st.selectbox(f"📌 Status", ["realizada", "cancelada"], index=["realizada", "cancelada"].index(row['status']), key=f"status_{row['id']}")
                novo_cobrar = st.checkbox(f"💸 Cobrar se cancelada", value=row['cobrar'], key=f"cobrar_{row['id']}")
                novo_pagamento = st.checkbox(f"✅ Pago", value=row['pagamento'], key=f"pago_{row['id']}")
                nova_nf = st.text_input("📑 Nota Fiscal", value=row.get('nota_fiscal', 'NF-'), key=f"nf_{row['id']}")
                novo_comentario = st.text_area("🗒️ Comentário", value=row.get('comentario', ''), key=f"coment_{row['id']}")

                if st.button(f"💾 Atualizar sessão {row['id']}", key=f"atualizar_{row['id']}"):
                    if not nova_nf.startswith("NF-"):
                        st.error("Nota Fiscal deve iniciar com 'NF-'")
                    else:
                        update_sessao(
                            row['id'],
                            novo_pagamento,
                            novo_valor,
                            novo_status,
                            novo_cobrar,
                            nova_nf,
                            novo_comentario
                        )
                        st.success("Sessão atualizada com sucesso.")
                        st.rerun()

                if st.button(f"🗑️ Excluir sessão {row['id']}", key=f"excluir_{row['id']}"):
                    excluir_sessao(row['id'])
                    st.success("Sessão excluída com sucesso.")
                    st.rerun()

        csv = sessoes_filtradas.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Exportar CSV", csv, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.csv", mime='text/csv')

        pdf_bytes = gerar_pdf_texto(sessoes_filtradas, cliente_nome, mes, ano)
        st.download_button("📄 Exportar PDF", pdf_bytes, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.pdf", mime='application/pdf')
    else:
        st.write(f"👩🏻‍⚕️ Psicóloga Responsavel: {psicologo['nome']}")
        st.info("Não existem clientes cadastrados na base de dados do psicólogo responsável")
