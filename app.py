import streamlit as st
from paginas.dashboard import show_dashboard
from paginas.novo_cliente import show_novo_cliente
from paginas.gerenciar_cliente import show_gerenciar_cliente
from paginas.user_edition import show_edicao_usuarios
from paginas.perfil import show_perfil
from db.functions import listar_clientes, select_user, validate_user
import base64
import time
import os

st.set_page_config(page_title="Neuropsicoclínica", page_icon="🧠", layout="wide")

from streamlit_cookies_manager import EncryptedCookieManager
# Gerenciador de cookies criptografado
cookies = EncryptedCookieManager(password=os.getenv("cookies_password"))

# ✅ Nova forma de ler a query string
pagina_atual = st.query_params.get("page")

# Inicializar estados
if "verificando_autenticacao" not in st.session_state:
    st.session_state.verificando_autenticacao = True
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "id_usuario" not in st.session_state:
    st.session_state.id_usuario = None
if "interface_pronta" not in st.session_state:
    st.session_state.interface_pronta = False

image_path = "assets/logo_neuro_sem_bk.png"

def process_base64_img(image_path):
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode()
        return encoded

def login():
    image_base64 = process_base64_img(image_path)
    st.markdown(f"""
        <div style="text-align: center;">
            <img src="data:image/png;base64,{image_base64}" width="300"/>
        </div>
        <hr style="margin-top: 20px; margin-bottom: 20px; border: 0.5px solid #ccc;"/>
        """, unsafe_allow_html=True)
    st.subheader("🔐 Login do Sistema")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        result = select_user(usuario, senha)
        if result:
            st.session_state.autenticado = True
            st.session_state.usuario_logado = usuario
            st.session_state.id_usuario = result["id"]

            cookies["user_id"] = str(result["id"])
            cookies["username"] = str(usuario)
            cookies["login_timestamp"] = str(time.time())
            cookies.save()

            st.success("✅ Login realizado com sucesso!")
            st.rerun()
        else:
            st.error("❌ Usuário ou senha incorretos. Tente novamente.")

    st.markdown("""
        <div style='font-size: small; color: gray; text-align: center; margin-top: 20px;'>
            🔒 Este sistema utiliza cookies para manter sua sessão ativa.
            Nenhum dado sensível é armazenado. Ao continuar, você concorda com nossa
            <a href='/?page=politica_de_privacidade'>Política de Privacidade</a>.
        </div>
    """, unsafe_allow_html=True)

def interface(privilegio, usuario):
    if not st.session_state.interface_pronta:
        with st.spinner("⏳ Carregando interface, por favor aguarde..."):
            psicologo_responsavel = usuario["psicologo_responsavel"]
            clientes = listar_clientes(psicologo_responsavel)
            st.session_state.psicologo_responsavel = psicologo_responsavel
            st.session_state._clientes = clientes
            st.session_state.interface_pronta = True
            st.rerun()
    else:
        psicologo_responsavel = st.session_state.psicologo_responsavel
        clientes = st.session_state._clientes

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
                "👤 Perfil",
                "✅ Edição de Usuários"
            ])
        else:
            pagina = st.sidebar.selectbox("Escolha uma opção", [
                "🏠 Página Inicial",
                "📄 Gerenciar Clientes",
                "➕ Novo Cliente",
                "👤 Perfil"
            ])

        if pagina == "🏠 Página Inicial":
            show_dashboard(psicologo_responsavel)
        elif pagina == "➕ Novo Cliente":
            show_novo_cliente(psicologo_responsavel)
        elif pagina == "📄 Gerenciar Clientes":
            show_gerenciar_cliente(psicologo_responsavel)
        elif pagina == "👤 Perfil":
            show_perfil()
        elif pagina == "✅ Edição de Usuários":
            show_edicao_usuarios()

        if "logout_triggered" not in st.session_state:
            st.session_state.logout_triggered = False
            st.session_state.logout_time = 0

        # Espaço para empurrar o botão para baixo
        st.sidebar.markdown("<br>", unsafe_allow_html=True)

        # Botão wide estilizado via HTML
        logout_clicked = st.sidebar.button("🚪 Sair", use_container_width=True)

        if logout_clicked:
            for key in ["user_id", "username", "login_timestamp"]:
                cookies[key] = ""
            cookies.save()

            st.session_state.autenticado = False
            st.session_state.usuario_logado = None
            st.session_state.id_usuario = None
            st.session_state.interface_pronta = False
            st.session_state.logout_triggered = True
            st.session_state.logout_time = time.time()

        if st.session_state.get("logout_triggered"):
            st.success("✅ Logout completo. Redirecionando...")
            time.sleep(2)
            st.session_state.logout_triggered = False
            st.rerun()

# ✅ Página de Política de Privacidade (query: ?page=politica_de_privacidade)
if pagina_atual == "politica_de_privacidade":
    from paginas.politica_de_privacidade import show_politica
    show_politica()
    st.stop()

# 🔐 Autenticação silenciosa com st.spinner
if not st.session_state.autenticado:
    if st.session_state.verificando_autenticacao and cookies.ready():
        with st.spinner("🔄 Verificando sessão ativa..."):
            user_id = cookies.get("user_id")
            username = cookies.get("username")
            ts_login = cookies.get("login_timestamp")

            if user_id and username and ts_login:
                if time.time() - float(ts_login) < 1800:
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = username
                    st.session_state.id_usuario = int(user_id)

            st.session_state.verificando_autenticacao = False
            st.rerun()
    elif st.session_state.verificando_autenticacao:
        st.spinner("🔄 Verificando sessão ativa...")
        st.stop()
    else:
        login()
        st.stop()

usuario = validate_user(st.session_state.id_usuario)
if usuario:
    privilegio = bool(usuario["privilegio"])
    interface(privilegio, usuario)
else:
    st.error("Usuário não encontrado.")
