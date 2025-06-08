import streamlit as st
from paginas.dashboard import show_dashboard
from paginas.novo_cliente import show_novo_cliente
from paginas.gerenciar_cliente import show_gerenciar_cliente
from db.functions import listar_clientes, select_user, validate_user
from paginas.user_edition import show_edicao_usuarios
import base64

# Inicializar estados
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "id_usuario" not in st.session_state:
    st.session_state.id_usuario = None

image_path = "assets/logo_neuro_sem_bk.png"

# Carrega e converte a imagem em base64
def process_base64_img(image_path):
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode()
        return encoded

# Função login
def login():
    st.set_page_config(page_title="Neuropsicoclínica",
    page_icon="🧠"  # ou uma imagem customizada (veja abaixo)
    )
    image_base64 = process_base64_img(image_path)
    # Exibe a imagem centralizada com HTML
    st.markdown(
        f"""
        <div style="text-align: center;">
            <img src="data:image/png;base64,{image_base64}" width="300"/>
        </div>
        <hr style="margin-top: 20px; margin-bottom: 20px; border: 0.5px solid #ccc;"/>
        """,
        unsafe_allow_html=True
    )
    st.subheader("🔐 Login do Sistema")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        result = select_user(usuario, senha)
        print(result)
        if result:
            st.session_state.autenticado = True
            st.session_state.usuario_logado = usuario
            st.session_state.id_usuario = result["id"]  # id está na primeira coluna
            st.success("✅ Login realizado com sucesso!")
            st.rerun()
        else:
            st.error("❌ Usuário ou senha incorretos. Tente novamente.")


# Interface principal
def interface(privilegio, usuario):
    st.set_page_config(page_title="Neuropsicoclínica",
    page_icon="🧠",  # ou uma imagem customizada (veja abaixo)
    layout="wide")
    col_logo, col_title = st.columns([1, 10])
    with col_logo:
        st.image("assets/logo_neuro_sem_bk.png", width=600)
    with col_title:
        st.write("--------------------------------------")

    st.sidebar.title("📂 Navegação")
    if privilegio:
        pagina = st.sidebar.selectbox("Escolha uma opção", [
            "🏠 Página Inicial",
            "📄 Gerenciar Clientes",
            "➕ Novo Cliente",
            "✅ Edição de Usuários"
        ])
    else:
        pagina = st.sidebar.selectbox("Escolha uma opção", [
            "🏠 Página Inicial",
            "📄 Gerenciar Clientes",
            "➕ Novo Cliente"
        ])
    psicologo_responsavel = usuario["psicologo_responsavel"]
    clientes = listar_clientes(psicologo_responsavel)
    cliente_selecionado = None
    if pagina == "📄 Gerenciar Clientes" and not clientes.empty:
        nome_busca = st.sidebar.text_input("🔎 Buscar cliente por nome")

        nomes_filtrados = clientes[clientes['nome'].str.contains(nome_busca, case=False, na=False)] if nome_busca else clientes

        if nomes_filtrados.empty:
            st.sidebar.warning("Nenhum cliente encontrado com esse nome.")
        else:
            cliente_selecionado = st.sidebar.selectbox(
                "👤 Selecione o cliente", 
                list(nomes_filtrados['nome'])
            )

    if pagina == "🏠 Página Inicial":
        show_dashboard(psicologo_responsavel)
    elif pagina == "➕ Novo Cliente":
        show_novo_cliente(psicologo_responsavel)
    elif pagina == "📄 Gerenciar Clientes" and cliente_selecionado:
        show_gerenciar_cliente(cliente_selecionado, psicologo_responsavel)
    elif pagina == "✅ Edição de Usuários":
        show_edicao_usuarios()

# Login obrigatório
if not st.session_state.autenticado:
    login()
    st.stop()

# Validar usuário logado
usuario = validate_user(st.session_state.id_usuario)
if usuario:
    privilegio = bool(usuario["privilegio"])
    interface(privilegio, usuario)
else:
    st.error("Usuário não encontrado.")
