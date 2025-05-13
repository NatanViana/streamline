# /pages/novo_cliente.py
import streamlit as st
from db.functions import adicionar_cliente

def show_novo_cliente(psicologo_responsavel):
    st.title("➕ Cadastro de Novo Cliente")
    with st.form("form_cliente"):
        nome = st.text_input("👤 Nome do cliente")
        valor = st.number_input("💰 Valor por sessão", min_value=0.0, step=10.0)
        submitted = st.form_submit_button("✅ Cadastrar Cliente")
        if submitted:
            if nome:
                adicionar_cliente(nome, valor, psicologo_responsavel)
                st.success(f"Cliente **{nome}** cadastrado com sucesso!")
            else:
                st.error("Por favor, preencha o nome do cliente.")
