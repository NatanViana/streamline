# /pages/gerenciar_cliente.py
import streamlit as st
from datetime import datetime
import pandas as pd
from db.functions import listar_clientes, sessoes_por_cliente, adicionar_sessao, excluir_cliente, excluir_sessao, update_sessao, listar_psicologos, upload_para_gcs, listar_arquivos_do_cliente, manual_load_dotenv, update_sessao_data_hora, atualizar_nome_cliente, gerar_pdf_pendencias, gerar_pdf_texto
import time
import os
import json
import unicodedata


MESES_PT = {
    "1": "Janeiro", "2": "Fevereiro", "3": "Março", "4": "Abril",
    "5": "Maio", "6": "Junho", "7": "Julho", "8": "Agosto",
    "9": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
    }   


# Utils bonitinhas
def _human_size(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def _pretty_dt(dt):
    try:
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return "-"

def render_lista_arquivos(bucket_name, pasta_cliente, tipo):
    with st.expander(f"📂 {tipo}", expanded=True):
        # --- CSS para os "cards"
        st.markdown("""
        <style>
        .file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
        .file-card {
            border: 1px solid rgba(0,0,0,0.06);
            border-radius: 16px;
            padding: 14px;
            background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(250,250,252,0.9));
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            transition: transform .12s ease, box-shadow .12s ease;
        }
        .file-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,0.06); }
        .file-title { font-weight: 600; font-size: 0.98rem; margin: 0 0 4px 0; line-height: 1.25; }
        .file-meta { color: #6b7280; font-size: 12.5px; margin-bottom: 10px; }
        .file-pill { display:inline-flex; align-items:center; gap:6px; font-size:12px; color:#374151; background:#EEF2FF; padding:6px 10px; border-radius:999px; }
        .file-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
        .file-actions { display:flex; gap:8px; }
        .btn-outline {
            border: 1px solid #E5E7EB; background: white; border-radius: 10px; padding: 8px 10px; font-size: 12.5px;
            cursor: pointer;
        }
        .btn-outline:hover { background: #F9FAFB; }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("**📄 Documentos salvos**")

        # Barra de busca + ordenação
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            termo = st.text_input("Pesquisar pelo nome", placeholder="Ex.: laudo, recibo, contrato…")
        with c2:
            criterio = st.selectbox("Ordenar por", ["Nome", "Data", "Tamanho"], index=1)
        with c3:
            reverso = st.toggle("Desc", value=True, help="Ordem decrescente")

        prefixo_busca = f"{pasta_cliente}/{tipo}/"
        blobs = listar_arquivos_do_cliente(bucket_name, prefixo_busca)

        if not blobs:
            st.info("Nenhum documento enviado ainda.")
            return

        # Normalizar dados
        items = []
        for blob in blobs:
            nome_full = blob.name.split("/")[-1]
            nome_amigavel = nome_full.replace(f"{tipo}_", "").replace("_", " ")
            # Alguns clientes do GCS têm atributos diferentes; tratamos defensivamente
            tamanho = getattr(blob, "size", None) or len(blob.download_as_bytes())
            atualizado = getattr(blob, "updated", None)
            items.append({
                "blob": blob,
                "nome_full": nome_full,
                "nome": nome_amigavel,
                "tamanho": tamanho,
                "updated": atualizado
            })

        # Filtro por busca
        if termo:
            t = termo.lower().strip()
            items = [i for i in items if t in i["nome"].lower() or t in i["nome_full"].lower()]

        # Ordenação
        if criterio == "Nome":
            keyf = lambda x: x["nome"].lower()
        elif criterio == "Data":
            keyf = lambda x: x["updated"] or datetime.min
        else:  # Tamanho
            keyf = lambda x: x["tamanho"] or 0

        items.sort(key=keyf, reverse=reverso)

        # Grid de cards
        st.markdown('<div class="file-grid">', unsafe_allow_html=True)
        for i, it in enumerate(items):
            blob = it["blob"]
            nome = it["nome"]
            nome_full = it["nome_full"]
            tam = _human_size(it["tamanho"] or 0)
            dt = _pretty_dt(it["updated"]) if it["updated"] else "-"

            # Baixar conteúdo apenas ao clicar no botão (lazy) usando callback simples
            # Como st.download_button exige bytes, faremos aqui — em listas grandes, considere cache.
            conteudo = blob.download_as_bytes()

            st.markdown(f"""
            <div class="file-card">
              <div class="file-row">
                <div class="file-pill">📕 PDF<span style="opacity:.7">•</span>{tam}</div>
                <div class="file-meta">{dt}</div>
              </div>
              <div class="file-title" title="{nome_full}">{nome}</div>
            """, unsafe_allow_html=True)

            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.download_button(
                    "⬇️ Baixar",
                    data=conteudo,
                    file_name=nome_full,
                    mime="application/pdf",
                    key=f"dl_{tipo}_{i}"
                )
            with col_b:
                # Botão extra (ex.: copiar nome) — opcional
                if st.button("🔗 Copiar nome", key=f"cp_{tipo}_{i}"):
                    st.toast(f"Nome copiado: {nome_full}")

            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

def gerar_horarios():
        horarios = []
        for h in range(8, 22):
            for m in [0, 30]:
                horarios.append(f"{h:02d}:{m:02d}")
        return horarios


def show_gerenciar_cliente(psicologo_responsavel):
    # --- Carregar dados
    clientes = listar_clientes(psicologo_responsavel)

    if clientes.empty:
        st.info("Nenhum cliente cadastrado.")
        st.stop()

    # Dicionário id->nome para exibição
    clientes['id'] = clientes['id'].astype(int)
    clientes['nome'] = clientes['nome'].astype(str)
    id2nome = dict(zip(clientes['id'], clientes['nome']))

    # Lista de IDs
    ids = clientes['id'].tolist()

    def remover_acentos(txt: str) -> str:
        if not isinstance(txt, str):
            return ""
        return ''.join(
            c for c in unicodedata.normalize('NFD', txt)
            if unicodedata.category(c) != 'Mn'
        )

    # Ordena IDs pelo nome (ignorando acentos e caixa)
    ids_ordenados = sorted(ids, key=lambda cid: remover_acentos(id2nome.get(cid, "")).lower())

    # Estado inicial do cliente selecionado (se ainda não existir ou não for válido, define para o 1º)
    sel_id = st.session_state.get('cliente_id')
    if sel_id not in ids_ordenados:
        sel_id = ids_ordenados[0]
        st.session_state['cliente_id'] = sel_id

    # Cálculo de índice SEM lançar exceção
    try:
        idx_atual = ids_ordenados.index(st.session_state['cliente_id'])
    except ValueError:
        idx_atual = 0

    # Selectbox
    st.session_state['cliente_id'] = st.sidebar.selectbox(
        "Cliente",
        options=ids_ordenados,
        index=idx_atual,
        format_func=lambda cid: id2nome.get(cid, f"ID {cid}")
    )

    cliente_id = st.session_state['cliente_id']

    # Buscar o cliente SEMPRE por ID (não por nome)
    cliente_row = clientes.loc[clientes['id'].astype(int) == int(cliente_id)]
    if cliente_row.empty:
        st.warning("Cliente não encontrado após atualização. Recarregue os dados.")
        st.stop()

    cliente = cliente_row.iloc[0]
    cliente_nome = str(cliente['nome'])

    # Cabeçalho
    psicologos_df = listar_psicologos()
    psicologo = psicologos_df[psicologos_df['id'] == psicologo_responsavel].iloc[0] if not psicologos_df.empty else {}
    st.title(f"🧑 Cliente: {cliente_nome}")
    st.write(f"👩🏻‍⚕️ Psicóloga Responsável: {psicologo.get('nome', 'N/A')}")

    # ====== Renomear paciente ======
    with st.expander("✏️ Alterar nome do paciente"):
        novo_nome = st.text_input("Novo nome do paciente", value=cliente_nome, key=f"novo_nome_{cliente_id}")

        if st.button("💾 Salvar novo nome", key=f"btn_salvar_nome_{cliente_id}"):
            try:
                atualizar_nome_cliente(cliente_id, novo_nome.strip())

                # Atualiza caches locais para a sessão atual
                id2nome[cliente_id] = novo_nome.strip()

                st.success("Nome atualizado com sucesso.")
                st.rerun()  # reexecuta, recarregando listar_clientes e exibindo o nome novo
            except ValueError as e:
                st.error(str(e))

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
    sessoes_faltas = sessoes_filtradas[sessoes_filtradas['status'] == "falta"]
    
    total_pagamento = sessoes_realizadas[sessoes_realizadas['pagamento'] != 0]['valor'].sum()
    total_pendente = sessoes_realizadas[sessoes_realizadas['pagamento']== 0]['valor'].sum() + sessoes_faltas[sessoes_faltas['cobrar'] == 1]['valor'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Realizadas", len(sessoes_realizadas))
    col2.metric("❌ Faltas", len(sessoes_faltas))
    col3.metric("💰 Recebido", f"R$ {total_pagamento:.2f}")
    col4.metric("🕗 Pendente", f"R$ {total_pendente:.2f}")

    # CSS para ajustar largura dos tabs
    st.markdown("""
        <style>
        .stTabs [role="tablist"] {
            justify-content: space-around;
        }
        .stTabs [data-baseweb="tab"] {
            flex: 1 1 25%;
            max-width: 25%;
            min-width: 25%;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

    tabs = st.tabs([ "📅 Sessões", "📁 Prontuários", "📝 Avaliação", "🧾 Notas Fiscais"])

   
    # Sessões
    with tabs[0]:

        st.markdown("### 🗓️ Registrar Nova Sessão")

        with st.form("form_sessao"):
            col1, col2 = st.columns(2)
            with col1:
                col11, col12 = st.columns(2)
                with col11:
                    data = st.date_input("📅 Data", datetime.today())
                with col12:
                    horarios = gerar_horarios()
                    hora = st.selectbox("🕒 Hora", horarios)
                    hora = datetime.strptime(hora, "%H:%M").time()
            with col2:
                col21, col22, col23 = st.columns(3)
                with col21:
                    valor = st.number_input("💵 Valor", min_value=0.0, value=float(cliente['valor_sessao']))
                with col22:
                    status = st.selectbox("📌 Status", ["realizada", "falta"])
                with col23:
                    cobrar = st.checkbox("💸 Cobrança de falta", value=False)
                    pagamento = st.checkbox("💸 Pago", value=False)

            col31, col32 = st.columns([2,1])
            with col31:
                observacao = st.text_input("📝 Observação", "")
            with col32:
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
                            conteudo, objetivo, material, atividade_casa, emocao_entrada, emocao_saida, proxima_sessao, observacao
                        )
                        st.success(f"Sessão em {data} às {hora} registrada com sucesso!")
                        time.sleep(0.5)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

        st.markdown("### 📅 Sessões Registradas")

        for _, row in sessoes_filtradas.iterrows():
            header = f"📍 {row['data'].date()} às {row['hora'].strftime('%H:%M')} - {row['status']}"
            with st.expander(header):

                # ====== FORM ÚNICO ======
                with st.form(key=f"form_{row['id']}"):
                    st.markdown("**🗓️ Horário de sessão**")
                    col1, col2 = st.columns(2)
                    with col1:
                        col11, col12 = st.columns(2)
                        with col11:
                            nova_data = st.date_input("Data", value=row['data'].date(), key=f"dt_{row['id']}")
                        with col12:
                            # seletor de hora
                            horarios = gerar_horarios()  # ex.: ["08:00","08:30",...]
                            hora_atual = row['hora'].strftime("%H:%M")
                            try:
                                idx_hora = horarios.index(hora_atual)
                            except ValueError:
                                idx_hora = 0  # fallback se hora_atual não estiver na lista
                            hora_sel = st.selectbox("Horário", horarios, index=idx_hora, key=f"hr_{row['id']}")
                            nova_hora = datetime.strptime(hora_sel, "%H:%M").time()
                    with col2:
                    # ====== Campos existentes ======
                        col21, col22, col23 = st.columns(3)
                        with col21:
                            novo_valor = st.number_input("💵 Valor", min_value=0.0, value=float(row['valor']), key=f"valor_{row['id']}")
                        with col22:
                            novo_status = st.selectbox("📌 Status", ["realizada", "falta"],
                                                index=["realizada", "falta"].index(row['status']),
                                                key=f"status_{row['id']}")
                        with col23:
                            novo_cobrar = st.checkbox("💸 Cobrança de falta", value=bool(row['cobrar']), key=f"cobrar_{row['id']}")
                            novo_pagamento = st.checkbox("✅ Pago", value=bool(row['pagamento']), key=f"pago_{row['id']}")

                    col31, col32 = st.columns([2,1])
                    with col31:
                        nova_obs = st.text_input("📝 Observação", value=row.get('observacao', ''), key=f"obs_{row['id']}")

                    with col32:
                        nova_nf = st.text_input("📑 Nota Fiscal", value=row.get('nota_fiscal', 'NF-'), key=f"nf_{row['id']}")

                    with st.popover("📔 Diário da Sessão"):
                        st.markdown("### 📔 Diário da Sessão")
                        novo_conteudo = st.text_area("🧠 Conteúdo", value=row.get('conteudo', ''), key=f"conteudo_{row['id']}")
                        novo_objetivo = st.text_area("🎯 Objetivo", value=row.get('objetivo', ''), key=f"objetivo_{row['id']}")
                        novo_material = st.text_area("📚 Material", value=row.get('material', ''), key=f"material_{row['id']}")
                        nova_atividade = st.text_area("🏠 Atividade para Casa", value=row.get('atividade_casa', ''), key=f"atividade_{row['id']}")

                        entrada_valor = int(row.get('emocao_entrada') or 3)
                        saida_valor = int(row.get('emocao_saida') or 3)

                        col_entrada, col_saida = st.columns(2)
                        with col_entrada:
                            entrada_str = st.radio("😊 Emoção na Entrada", opcoes_emocao,
                                                index=max(0, entrada_valor - 1), horizontal=True, key=f"entrada_{row['id']}")
                            nova_emocao_entrada = int(entrada_str.split()[0])
                        with col_saida:
                            saida_str = st.radio("😌 Emoção na Saída", opcoes_emocao,
                                                index=max(0, saida_valor - 1), horizontal=True, key=f"saida_{row['id']}")
                            nova_emocao_saida = int(saida_str.split()[0])

                        nova_proxima = st.text_area("🗓️ Planejamento Próxima Sessão", value=row.get('proxima_sessao', ''), key=f"proxima_{row['id']}")

                    # ====== Botão ÚNICO ======
                    submitted = st.form_submit_button(f"💾 Atualizar sessão")
                    if submitted:
                        if not nova_nf.startswith("NF-"):
                            st.error("Nota Fiscal deve iniciar com 'NF-'")
                        else:
                            try:
                                # Atualiza data/hora SOMENTE se mudou
                                mudou_data_hora = (nova_data != row['data'].date()) or (nova_hora != row['hora'])
                                if mudou_data_hora:
                                    update_sessao_data_hora(row['id'], nova_data, nova_hora)

                                # Atualiza demais campos
                                update_sessao(
                                    row['id'], novo_pagamento, float(novo_valor), novo_status, int(novo_cobrar), nova_nf,
                                    novo_conteudo, novo_objetivo, novo_material, nova_atividade,
                                    int(nova_emocao_entrada), int(nova_emocao_saida), nova_proxima, nova_obs
                                )
                                st.success("Sessão atualizada com sucesso.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                            except Exception as e:
                                st.error(f"Erro ao atualizar a sessão: {e}")

                if st.button(f"🗑️ Excluir sessão", key=f"excluir_{row['id']}"):
                    excluir_sessao(row['id'])
                    st.success("Sessão excluída com sucesso.")
                    st.rerun()

        #csv = sessoes_filtradas.to_csv(index=False).encode('utf-8')
        #st.download_button("⬇️ Exportar CSV", csv, file_name=f"sessoes_{cliente_nome}_{mes}_{ano}.csv", mime='text/csv')

        st.markdown("## 📄 Relatórios")

        tab_mensal, tab_pend = st.tabs(["🗓️ Mensal de Sessões", "⚠️ Pendências Globais"])

        with tab_mensal:
            st.markdown("### 🗓️ Exportar relatório mensal de sessões")
            finalidade = st.selectbox(
                "Escolha para quem será o relatório de sessão:",
                ["Cliente", "Psicólogo"],
                key="finalidade_mensal"
            )
            pdf_bytes_mensal = gerar_pdf_texto(sessoes_filtradas, cliente_nome, mes, ano, finalidade)
            nome_arquivo_mensal = f"sessoes_{cliente_nome}_{mes}_{ano}.pdf".replace(" ", "_")
            st.download_button(
                "📄 Exportar PDF",
                pdf_bytes_mensal,
                file_name=nome_arquivo_mensal,
                mime="application/pdf",
                key="btn_export_mensal"
            )

        with tab_pend:
            st.markdown("### ⚠️ Exportar relatório de pendências de sessões (global)")
            pdf_bytes_pend = gerar_pdf_pendencias(sessoes, cliente_nome)
            nome_arquivo_pend = f"pendencias_{cliente_nome}.pdf".replace(" ", "_")
            st.download_button(
                "📄 Exportar Pendências PDF",
                pdf_bytes_pend,
                file_name=nome_arquivo_pend,
                mime="application/pdf",
                key="btn_export_pend"
            )

    
    
    
    # Prontuários
    with tabs[1]:
        st.subheader("📁 Documentos do Cliente")

        bucket_name = os.getenv("GCS_BUCKET_NAME")
        pasta_cliente = f"{cliente_nome}"  # usado como prefixo no GCS

        tipos = {
            "Questionários": "🔵",      # azul
            "Testes Corrigidos": "🟢",  # verde
            "Laudos": "🟠",             # laranja
            "Contrato": "🔴"            # vermelho
        }

        for tipo, icone in tipos.items():
            with st.expander(f"{icone} {tipo}"):
                st.markdown(f"**Enviar novo documento para {tipo}:**")
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
    
    # Notas Fiscais
    with tabs[3]:
        st.subheader("📁 Notas Fiscais")

        tipos = ["Notas Fiscais"]
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        pasta_cliente = f"{cliente_nome}"  # usado como prefixo no GCS

        for tipo in tipos:
            with st.expander(f"📥 Submeter {tipo}", expanded=False):
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

            with st.expander(f"📂 {tipo}", expanded=True):
                prefixo_busca = f"{pasta_cliente}/{tipo}/"
                arquivos = listar_arquivos_do_cliente(bucket_name, prefixo_busca)

                if arquivos:
                    for i, blob in enumerate(arquivos):
                        arquivo_nome = blob.name.split("/")[-1]
                        nome_amigavel = arquivo_nome.replace(f"{tipo}_", "").replace("_", " ")
                        conteudo = blob.download_as_bytes()
                        tamanho = getattr(blob, "size", None) or len(conteudo)
                        atualizado = getattr(blob, "updated", None)

                        col1, col2 = st.columns([4,1])  # mais espaço pro nome
                        with col1:
                            st.write(f"📕 **{nome_amigavel}**")
                            st.caption(f"{tamanho//1024} KB • {atualizado if atualizado else '-'}")
                        with col2:
                            st.download_button(
                                "⬇ Baixar",
                                data=conteudo,
                                file_name=arquivo_nome,
                                mime="application/pdf",
                                key=f"dl_{tipo}_{i}"
                            )
                        st.divider()  # linha separadora
                else:
                    st.info("Nenhum documento enviado ainda.")