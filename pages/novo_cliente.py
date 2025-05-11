# /pages/novo_cliente.py
import streamlit as st
from db.functions import adicionar_cliente
from pages.gerenciar_cliente import show_gerenciar_cliente


def show_novo_cliente():
    st.title("➕ Cadastro de Novo Cliente")
    with st.form("form_cliente"):
        nome = st.text_input("👤 Nome do cliente")
        valor = st.number_input("💰 Valor por sessão", min_value=0.0, step=10.0)
        submitted = st.form_submit_button("✅ Cadastrar Cliente")
        if submitted:
            if nome:
                client_id = adicionar_cliente(nome, valor)
                st.success(f"Cliente **{nome}** cadastrado com sucesso!")
                show_gerenciar_cliente(client_id)
            else:
                st.error("Por favor, preencha o nome do cliente.")
