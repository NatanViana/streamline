# /pages/gerenciar_cliente.py
import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from db.functions import listar_clientes, sessoes_por_cliente, adicionar_sessao, excluir_cliente, excluir_sessao, update_sessao, listar_psicologos, upload_para_gcs, listar_arquivos_do_cliente, manual_load_dotenv
import time
import os
import json

def gerar_horarios():
        horarios = []
        for h in range(0, 24):
            for m in [0, 30]:
                horarios.append(f"{h:02d}:{m:02d}")
        return horarios

def gerar_pdf_texto(sessoes, cliente_nome, mes, ano, finalidade):
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
        if finalidade != 'Cliente':
            pdf.cell(200, 10, txt=f"Status: {row['status']} | Cobrar se cancelada: {'Sim' if row['cobrar'] else 'Não'}", ln=True)
        else:
            pdf.cell(200, 10, txt=f"Status: {row['status']}", ln=True)
        pdf.cell(200, 10, txt=f"Pendente de Pagamento: {'Sim' if row['pagamento'] else 'Não'}", ln=True)

        # Nota Fiscal
        nota_fiscal = row.get('nota_fiscal') or 'NF- N/D'
        pdf.cell(200, 10, txt=f"Nota Fiscal: {nota_fiscal}", ln=True)
        if finalidade != 'Cliente':
            pdf.cell(200, 10, txt=f"--------- Diário de Sessão ----------------", ln=True)

            # Campos adicionais
            pdf.multi_cell(0, 10, txt=f"Conteúdo: {row.get('conteudo') or 'Não registrado'}")
            pdf.multi_cell(0, 10, txt=f"Objetivo: {row.get('objetivo') or 'Não registrado'}")
            pdf.multi_cell(0, 10, txt=f"Material: {row.get('material') or 'Não registrado'}")
            pdf.multi_cell(0, 10, txt=f"Atividade para Casa: {row.get('atividade_casa') or 'Não registrada'}")
            
            entrada = row.get('emocao_entrada')
            saida = row.get('emocao_saida')
            pdf.cell(200, 10, txt=f"Emoção Entrada: {entrada if entrada is not None else 'N/D'} | Emoção Saída: {saida if saida is not None else 'N/D'}", ln=True)

            pdf.multi_cell(0, 10, txt=f"Próxima Sessão: {row.get('proxima_sessao') or 'Não registrada'}")

        pdf.cell(200, 10, txt=f"-----------------------------------------", ln=True)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin1')

def show_gerenciar_cliente(cliente_nome, psicologo_responsavel):
    clientes = listar_clientes(psicologo_responsavel)
    cliente = clientes[clientes['nome'] == cliente_nome].iloc[0]
    cliente_id = int(cliente['id'])
    psicologos_df = listar_psicologos()
    psicologo = psicologos_df[psicologos_df['id'] == psicologo_responsavel].iloc[0] if not psicologos_df.empty else {}

    st.title(f"🧑 Cliente: {cliente_nome}")
    st.write(f"👩🏻‍⚕️ Psicóloga Responsável: {psicologo.get('nome', 'N/A')}")

    with st.expander("⚠️ Excluir Cliente"):
        st.warning("Esta ação é irreversível. Todos os dados do cliente serão removidos.")
        confirmar = st.checkbox(f"Confirmo que desejo excluir o cliente: {cliente_nome}")

        if confirmar and st.button("❌ Excluir Cliente Permanentemente"):
            excluir_cliente(cliente_id)
            st.success(f"Cliente {cliente_nome} excluído com sucesso.")
            st.session_state['pagina'] = "🏠 Página Inicial"
            st.rerun()

    

    st.subheader("📊 Indicadores do Cliente")
    sessoes = sessoes_por_cliente(cliente_id)
    sessoes['data'] = pd.to_datetime(sessoes['data'])
    if pd.api.types.is_timedelta64_dtype(sessoes['hora']):
        sessoes['hora'] = sessoes['hora'].apply(lambda td: (pd.Timestamp('00:00:00') + td).time())
        
    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox("📅 Mês", list(range(1, 13)), index=datetime.now().month - 1)
    with col2:
        anos_disponiveis = sessoes['data'].dt.year.unique().tolist()
        ano = st.selectbox("📆 Ano", sorted(anos_disponiveis, reverse=True) if anos_disponiveis else [datetime.now().year])

    sessoes_filtradas = sessoes[(sessoes['data'].dt.month == mes) & (sessoes['data'].dt.year == ano)]

    # Certifique-se de que a coluna `hora` está sendo convertida corretamente
    sessoes_filtradas['hora'] = pd.to_datetime(sessoes_filtradas['hora'].astype(str)).dt.time

    sessoes_realizadas = sessoes_filtradas[sessoes_filtradas['status'] == "realizada"]
    sessoes_canceladas = sessoes_filtradas[sessoes_filtradas['status'] == "cancelada"]
    
    total_pagamento = sessoes_realizadas[sessoes_realizadas['pagamento'] != 0]['valor'].sum()
    total_pendente = sessoes_realizadas[sessoes_realizadas['pagamento']== 0]['valor'].sum() + sessoes_canceladas[sessoes_canceladas['cobrar'] == 1]['valor'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Realizadas", len(sessoes_realizadas))
    col2.metric("❌ Canceladas", len(sessoes_canceladas))
    col3.metric("💰 Recebido", f"R$ {total_pagamento:.2f}")
    col4.metric("🕗 Pendente", f"R$ {total_pendente:.2f}")

    # CSS para ajustar largura dos tabs
    st.markdown("""
        <style>
        .stTabs [role="tablist"] {
            justify-content: space-around;
        }
        .stTabs [data-baseweb="tab"] {
            flex: 1 1 30%;
            max-width: 30%;
            min-width: 30%;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

    tabs = st.tabs([ "📅 Sessões", "📁 Prontuários", "📝 Avaliação"])

   
    # Sessões
    with tabs[0]:

        st.markdown("### 🗓️ Registrar Nova Sessão")

        with st.form("form_sessao"):
            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("📅 Data", datetime.today())
                horarios = gerar_horarios()
                hora = st.selectbox("🕒 Hora", horarios)
                hora = datetime.strptime(hora, "%H:%M").time()
            with col2:
                valor = st.number_input("💵 Valor", min_value=0.0, value=float(cliente['valor_sessao']))
                status = st.selectbox("📌 Status", ["realizada", "cancelada"])
                cobrar = st.checkbox("💸 Cobrar se cancelada", value=False)
                pagamento = st.checkbox("💸 Pago", value=False)

            nota_fiscal = st.text_input("📑 Nota Fiscal (Comece com NF-)", "NF-")

            emocoes = {
                1: "😢",
                2: "🙁",
                3: "😐",
                4: "🙂",
                5: "😄"
            }
            opcoes_emocao = [f"{i} {emocoes[i]}" for i in range(1, 6)]

            with st.expander("📔 Diário da Sessão"):
                conteudo = st.text_area("🧠 Conteúdo", "")
                objetivo = st.text_area("🎯 Objetivo", "")
                material = st.text_area("📚 Material", "")
                atividade_casa = st.text_area("🏠 Atividade para Casa", "")

                col_entrada, col_saida = st.columns(2)
                with col_entrada:
                    entrada_str = st.radio("😊 Emoção na Entrada", opcoes_emocao, index=2, horizontal=True)
                    emocao_entrada = int(entrada_str.split()[0])
                with col_saida:
                    saida_str = st.radio("😌 Emoção na Saída", opcoes_emocao, index=2, horizontal=True)
                    emocao_saida = int(saida_str.split()[0])

                proxima_sessao = st.text_area("🗓️ Planejamento Próxima Sessão", "")

            if st.form_submit_button("📂 Salvar Sessão"):
                if not nota_fiscal.startswith("NF-"):
                    st.error("Nota Fiscal deve iniciar com 'NF-'")
                else:
                    try:
                        adicionar_sessao(
                            cliente_id, str(data), hora, valor, status, cobrar, pagamento, nota_fiscal,
                            conteudo, objetivo, material, atividade_casa, emocao_entrada, emocao_saida, proxima_sessao
                        )
                        st.success(f"Sessão em {data} às {hora} registrada com sucesso!")
                        time.sleep(0.5)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

        st.markdown("### 📅 Sessões Registradas")

        for _, row in sessoes_filtradas.iterrows():
            with st.expander(f"📍 {row['data'].date()} às {(row['hora']).strftime('%H:%M')} - {row['status']}"):
                novo_valor = st.number_input("💵 Valor", min_value=0.0, value=row['valor'], key=f"valor_{row['id']}")
                novo_status = st.selectbox("📌 Status", ["realizada", "cancelada"], index=["realizada", "cancelada"].index(row['status']), key=f"status_{row['id']}")
                novo_cobrar = st.checkbox("💸 Cobrar se cancelada", value=row['cobrar'], key=f"cobrar_{row['id']}")
                novo_pagamento = st.checkbox("✅ Pago", value=row['pagamento'], key=f"pago_{row['id']}")
                nova_nf = st.text_input("📑 Nota Fiscal", value=row.get('nota_fiscal', 'NF-'), key=f"nf_{row['id']}")

                with st.popover("📔 Diário da Sessão"):
                    st.markdown("###📔 Diário da Sessão")
                    novo_conteudo = st.text_area("🧠 Conteúdo", value=row.get('conteudo', ''), key=f"conteudo_{row['id']}")
                    novo_objetivo = st.text_area("🎯 Objetivo", value=row.get('objetivo', ''), key=f"objetivo_{row['id']}")
                    novo_material = st.text_area("📚 Material", value=row.get('material', ''), key=f"material_{row['id']}")
                    nova_atividade = st.text_area("🏠 Atividade para Casa", value=row.get('atividade_casa', ''), key=f"atividade_{row['id']}")

                    entrada_valor = row.get('emocao_entrada') or 3
                    saida_valor = row.get('emocao_saida') or 3

                    col_entrada, col_saida = st.columns(2)
                    with col_entrada:
                        entrada_str = st.radio("😊 Emoção na Entrada", opcoes_emocao, index=entrada_valor - 1, horizontal=True, key=f"entrada_{row['id']}")
                        nova_emocao_entrada = int(entrada_str.split()[0])
                    with col_saida:
                        saida_str = st.radio("😌 Emoção na Saída", opcoes_emocao, index=saida_valor - 1, horizontal=True, key=f"saida_{row['id']}")
                        nova_emocao_saida = int(saida_str.split()[0])

                    nova_proxima = st.text_area("🗓️ Planejamento Próxima Sessão", value=row.get('proxima_sessao', ''), key=f"proxima_{row['id']}")

                if st.button(f"💾 Atualizar sessão {row['id']}", key=f"atualizar_{row['id']}"):
                    if not nova_nf.startswith("NF-"):
                        st.error("Nota Fiscal deve iniciar com 'NF-'")
                    else:
                        update_sessao(
                            row['id'], novo_pagamento, novo_valor, novo_status, novo_cobrar, nova_nf,
                            novo_conteudo, novo_objetivo, novo_material, nova_atividade,
                            nova_emocao_entrada, nova_emocao_saida, nova_proxima
                        )
                        st.success("Sessão atualizada com sucesso.")
                        st.rerun()

                if st.button(f"🗑️ Excluir sessão {row['id']}", key=f"excluir_{row['id']}"):
                    excluir_sessao(row['id'])
                    st.success("Sessão excluída com sucesso.")
                    st.rerun()

        #csv = sessoes_filtradas.to_csv(index=False).encode('utf-8')
        #st.download_button("⬇️ Exportar CSV", csv, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.csv", mime='text/csv')

        st.markdown("### 🗓️ Exportar relatório mensal de sessões")
        finalidade = st.selectbox("Escolha para quem será o relatório de sessão...",['Cliente','Psicólogo'])
        pdf_bytes = gerar_pdf_texto(sessoes_filtradas, cliente_nome, mes, ano, finalidade)
        st.download_button("📄 Exportar PDF", pdf_bytes, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.pdf", mime='application/pdf')
    

    # Prontuários
    with tabs[1]:
        st.subheader("📁 Documentos do Cliente")

        tipos = ["Questionários", "Testes Corrigidos", "Laudos", "Contrato"]
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        pasta_cliente = f"{cliente_nome}"  # usado como prefixo no GCS

        for tipo in tipos:
            with st.expander(f"📂 {tipo}"):
                st.markdown("**Enviar novo documento:**")
                nome_personalizado = st.text_input(f"Nome do arquivo ({tipo})", key=f"{tipo}_nome")

                uploaded_file = st.file_uploader(
                    f"Arraste ou selecione um arquivo PDF para {tipo}",
                    type=["pdf"],
                    key=f"{tipo}_upload"
                )

                submissao = st.button("✅ Submeter", key=f"button_{tipo}_nome")

                if uploaded_file and nome_personalizado and submissao:
                    nome_limpo = nome_personalizado.strip().replace(" ", "_")
                    extensao = os.path.splitext(uploaded_file.name)[1]
                    nome_final = f"{tipo}_{nome_limpo}{extensao}"
                    blob_path = f"{pasta_cliente}/{tipo}/{nome_final}"

                    url = upload_para_gcs(bucket_name, blob_path, uploaded_file)
                    st.success(f"{tipo} enviado para o bucket como: {nome_final}")

                elif uploaded_file and not nome_personalizado:
                    st.warning("⚠️ Por favor, informe um nome para o arquivo antes de enviar.")
                
                # Mostrar arquivos já enviados
                st.markdown("**📄 Documentos salvos:**")

                # Caminho correto: dentro da subpasta do tipo (ex: "joao_123/Laudos/")
                prefixo_busca = f"{pasta_cliente}/{tipo}/"
                arquivos = listar_arquivos_do_cliente(bucket_name, prefixo_busca)

                # Nenhum filtro extra necessário — GCS já retorna só os arquivos dessa "pasta"
                if arquivos:
                    for blob in arquivos:
                        arquivo_nome = blob.name.split("/")[-1]
                        nome_amigavel = arquivo_nome.replace(f"{tipo}_", "").replace("_", " ")
                        conteudo = blob.download_as_bytes()

                        st.download_button(
                            label=f"⬇️ {nome_amigavel}",
                            data=conteudo,
                            file_name=arquivo_nome,
                            mime="application/pdf"
                        )
                else:
                    st.info("Nenhum documento enviado ainda.")

    # Avaliação
    with tabs[2]:
        st.subheader("📝 Avaliações Clínicas")
        data_avaliacao = st.date_input("📅 Data da Avaliação", datetime.today())
        tags = st.text_input("🔖 Tags (ex: ansiedade, evolução positiva)")
        texto = st.text_area("📋 Descrição da Avaliação")

        if st.button("💾 Salvar Avaliação"):
            avaliacao = {"data": str(data_avaliacao), "tags": tags, "descricao": texto}
            path = f"avaliacoes/{cliente_id}.json"
            os.makedirs("avaliacoes", exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(avaliacao) + "\n")
            st.success("Avaliação salva com sucesso.")