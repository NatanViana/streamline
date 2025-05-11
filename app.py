# Estrutura de um projeto organizado para o app de gestão de clientes com Streamlit e DuckDB

# ============================
# /app.py (arquivo principal)
# ============================

import streamlit as st
from pages.dashboard import show_dashboard
from pages.novo_cliente import show_novo_cliente
from pages.gerenciar_cliente import show_gerenciar_cliente
from db.functions import listar_clientes



# Sidebar de navegação
st.set_page_config(layout="wide")

# Logo no topo
# col_logo, col_title = st.columns([1, 10])
# with col_logo:
#     st.image("assets/logo.png", width=600)
# with col_title:
#     st.markdown("<h1 margin-top: 30px;'>Instituto Amplamente</h1>", # unsafe_allow_html=True)

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


