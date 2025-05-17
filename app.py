import streamlit as st
from pages.dashboard import show_dashboard
from pages.novo_cliente import show_novo_cliente
from pages.gerenciar_cliente import show_gerenciar_cliente
from db.functions import listar_clientes, select_user, validate_user
from pages.user_edition import show_edicao_usuarios

# Inicializar estados
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "id_usuario" not in st.session_state:
    st.session_state.id_usuario = None

# Função login
def login():
    st.title("🔐 Login do Sistema")
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
    st.set_page_config(layout="wide")
    col_logo, col_title = st.columns([1, 10])
    with col_logo:
        st.image("assets/logo_neuro.png", width=600)
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
        cliente_selecionado = st.sidebar.selectbox("👤 Selecione o cliente", list(clientes['nome']))

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
