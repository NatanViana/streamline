# Estrutura de um projeto organizado para o app de gestão de clientes com Streamlit e DuckDB

# ============================
# /app.py (arquivo principal)
# ============================

import streamlit as st
from pages.dashboard import show_dashboard
from pages.novo_cliente import show_novo_cliente
from pages.gerenciar_cliente import show_gerenciar_cliente
from db.functions import listar_clientes

# Simulação de banco de usuários (substitua por banco real se quiser)
USUARIOS = {
    "usuario": "noelia",
    "senha": "123"
}

# Inicializar estado de autenticação
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "tentativas" not in st.session_state:
    st.session_state.tentativas = 0

def login():
    st.title("🔐 Login do Sistema")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario in USUARIOS and USUARIOS["senha"] == senha:
            st.session_state.autenticado = True
            st.success("✅ Login realizado com sucesso!")
            st.rerun()
        else:
            st.session_state.tentativas += 1
            st.error("❌ Usuário ou senha incorretos. Tente novamente.")
            if st.session_state.tentativas >= 3:
                st.info("🔐 Não possui conta? Solicite cadastro ao administrador.")

# Se não estiver autenticado, mostra a tela de login
if not st.session_state.autenticado:
    login()
    st.stop()

# Sidebar de navegação
st.set_page_config(layout="wide")

# Logo no topo
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image("assets/logo_neuro.png", width=600)
with col_title:
    st.write("--------------------------------------")

st.sidebar.title("📂 Navegação")
pagina = st.sidebar.selectbox("Escolha uma opção", [
    "🏠 Página Inicial",
    "📄 Gerenciar Clientes",
    "➕ Novo Cliente"
])

clientes = listar_clientes()
cliente_selecionado = None
if pagina == "📄 Gerenciar Clientes" and not clientes.empty:
    cliente_selecionado = st.sidebar.selectbox("👤 Selecione o cliente", list(clientes['nome']))

# Roteamento das páginas
if pagina == "🏠 Página Inicial":
    show_dashboard()
elif pagina == "➕ Novo Cliente":
    show_novo_cliente()
elif pagina == "📄 Gerenciar Clientes" and cliente_selecionado:
    show_gerenciar_cliente(cliente_selecionado)


