# 📚 Coletânea de Documentos (Modelos)
import os
import os.path
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from db.functions import listar_arquivos_do_cliente, upload_para_gcs

TZ_FORTALEZA = ZoneInfo("America/Fortaleza")

def show_modelos():
    # ---------- Estilo ----------
    st.markdown("""
    <style>
    .block-container{padding-top:1.5rem;padding-bottom:3rem}
    hr.soft{border:none;border-top:1px solid #eef1f5;margin:0.75rem 0 1rem}
    .file-card{
        padding:0.6rem 0.9rem;border:1px solid #e9edf3;border-radius:12px;
        background:#fff; color:#111;  /* texto preto no card */
    }
    .file-row + .file-row{margin-top:0.5rem}
    .caption-aux{color:#6b7280}
    /* Tabs 30% cada (3 tabs ~90%) */
    .stTabs [data-baseweb="tab-list"]{justify-content:flex-start;gap:1rem}
    .stTabs [data-baseweb="tab"]{flex:0 0 30% !important;max-width:30% !important}
    </style>
    """, unsafe_allow_html=True)

    # ---------- Parametrização ----------
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    BASE_PREFIX = "modelos"  # modelos/<Tipo>/
    CATEGORIAS = {"Testes":"🧪","Laudos":"📝","Contratos":"📄"}

    # ---------- Header ----------
    st.title("📚 Coletânea de Documentos (Modelos)")
    st.markdown("Envie PDFs de **modelos** e acesse os já salvos por categoria.")

    # Tabs
    tab_objs = st.tabs([f"{icone} {nome}" for nome, icone in CATEGORIAS.items()])

    for (tipo, icone), tab in zip(CATEGORIAS.items(), tab_objs):
        with tab:
            # ===== Envio (separado da lista) =====
            st.markdown(f"### 📥 Enviar modelo para **{tipo}**")
            with st.container(border=True):
                nome_personalizado = st.text_input(f"Nome do arquivo ({tipo})", key=f"nome_{tipo}")
                uploaded_file = st.file_uploader(
                    f"Arraste/Selecione um PDF para {tipo}",
                    type=["pdf"],
                    key=f"upload_{tipo}",
                )
                enviar = st.button("✅ Submeter", key=f"btn_{tipo}", use_container_width=True)

                if enviar:
                    if not bucket_name:
                        st.error("Bucket não configurado. Defina `GCS_BUCKET_NAME` no ambiente.")
                    elif not uploaded_file:
                        st.warning("Selecione um arquivo PDF.")
                    elif not nome_personalizado:
                        st.warning("Informe um nome para o arquivo.")
                    else:
                        extensao = os.path.splitext(uploaded_file.name)[1] or ".pdf"
                        if extensao.lower() != ".pdf":
                            extensao = ".pdf"
                        nome_limpo = nome_personalizado.strip().replace(" ", "_")
                        nome_final = f"{tipo}_{nome_limpo}{extensao}"
                        blob_path = f"{BASE_PREFIX}/{tipo}/{nome_final}"
                        try:
                            _ = upload_para_gcs(bucket_name, blob_path, uploaded_file)
                            st.success(f"Enviado como **{nome_final}**.")
                            st.caption(f"gs://{bucket_name}/{blob_path}")
                        except Exception as e:
                            st.error(f"Falha ao enviar: {e}")

            st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

            # ===== Lista =====
            st.markdown(f"### 📖 Modelos de **{tipo}**")

            # ---------------- Filtros e seleção ----------------
            st.markdown("#### 🎛️ Filtros e seleção")
            with st.container(border=True):
                col_f1, col_f2, col_f3, col_f4 = st.columns([3,1.5,1.2,1])
                with col_f1:
                    filtro_local = st.text_input(
                        "Filtrar por nome",
                        key=f"flt_{tipo}",
                        placeholder="ex.: consentimento"
                    )
                with col_f2:
                    ordenar_por = st.selectbox(
                        "Ordenar por",
                        ["Data (recente → antigo)", "Nome (A→Z)"],
                        key=f"ord_{tipo}",
                    )
                with col_f3:
                    page_size_label = st.selectbox(
                        "Itens/página", [10, 20, 50, "Todos"], key=f"ps_{tipo}"
                    )
                    page_size = None if page_size_label == "Todos" else int(page_size_label)
                with col_f4:
                    if st.button("🔄 Recarregar", key=f"reload_{tipo}", use_container_width=True):
                        st.rerun()

            # ---------------- Carregamento/Processamento ----------------
            prefixo_busca = f"{BASE_PREFIX}/{tipo}/"
            try:
                arquivos = listar_arquivos_do_cliente(bucket_name, prefixo_busca)
            except Exception as e:
                arquivos = []
                st.error(f"Não foi possível listar arquivos: {e}")

            itens = []
            termo = (filtro_local or "").strip().lower()
            for blob in arquivos or []:
                arquivo_nome = blob.name.split("/")[-1]
                if not arquivo_nome.lower().endswith(".pdf"):
                    continue
                if termo and termo not in arquivo_nome.lower():
                    continue

                nome_amigavel = arquivo_nome.replace(f"{tipo}_", "").replace("_", " ")

                # Tamanho
                try:
                    tamanho_bytes = getattr(blob, "size", None)
                    tamanho_leg = f"{tamanho_bytes//1024} KB" if tamanho_bytes else "-"
                except Exception:
                    tamanho_leg = "-"

                # Data (UTC-3 Fortaleza)
                try:
                    atualizado = getattr(blob, "updated", None)
                    if isinstance(atualizado, datetime):
                        atualizado_leg = atualizado.astimezone(TZ_FORTALEZA).strftime("%d/%m/%Y %H:%M")
                    else:
                        atualizado_leg = "-"
                except Exception:
                    atualizado = None
                    atualizado_leg = "-"

                itens.append({
                    "blob": blob,
                    "arquivo_nome": arquivo_nome,
                    "nome_amigavel": nome_amigavel,
                    "tamanho": tamanho_leg,
                    "updated": atualizado,
                    "updated_leg": atualizado_leg,
                })

            # Ordenação
            if ordenar_por.startswith("Data"):
                itens.sort(key=lambda x: x["updated"] or datetime.min, reverse=True)
            else:
                itens.sort(key=lambda x: x["arquivo_nome"].lower())

            # ---------------- Lista de documentos ----------------
            st.markdown("#### 📚 Lista de documentos")

            total = len(itens)
            if total == 0:
                st.info("Nenhum documento encontrado.")
            else:
                max_pages = 1 if (page_size is None) else (total - 1) // page_size + 1
                page = 1
                if max_pages > 1:
                    page = st.slider("Página", 1, max_pages, 1, key=f"pg_{tipo}")

                start = 0 if page_size is None else (page - 1) * page_size
                end = total if page_size is None else min(start + page_size, total)
                visiveis = itens[start:end]

                for i, it in enumerate(visiveis):
                    conteudo = it["blob"].download_as_bytes()
                    with st.container():
                        c1, c2, c3, c4 = st.columns([6,2,2,2], vertical_alignment="center")
                        with c1:
                            st.markdown(
                                f"<div class='file-card file-row'>📕 <b>{it['nome_amigavel']}</b></div>",
                                unsafe_allow_html=True
                            )
                        with c2:
                            st.caption(f"📦 {it['tamanho']}")
                        with c3:
                            st.caption(f"🕒 {it['updated_leg']} (UTC−3)")
                        with c4:
                            st.download_button(
                                "⬇️ Baixar",
                                data=conteudo,
                                file_name=it["arquivo_nome"],
                                mime="application/pdf",
                                key=f"dl_{tipo}_{start+i}",
                                use_container_width=True
                            )

                st.caption(f"Mostrando {len(visiveis)} de {total} arquivo(s).")