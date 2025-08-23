import streamlit as st
from db.functions import adicionar_cliente

def show_novo_cliente(psicologo_responsavel):
    st.title("➕ Cadastro de Novo Cliente")
    with st.form("form_cliente"):
        nome = st.text_input("👤 Nome do cliente")
        valor = st.number_input("💰 Valor por sessão", min_value=0.0, step=10.0)

        dia_agendamento = st.selectbox(
            "📅 Dia de agendamento",
            ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira","Indefinido"]
        )

        submitted = st.form_submit_button("✅ Cadastrar Cliente")
        if submitted:
            if nome:
                # Você pode adaptar a função adicionar_cliente para receber o dia de agendamento também
                adicionar_cliente(nome, valor, psicologo_responsavel, dia_agendamento)
                st.success(f"Cliente **{nome}** cadastrado com sucesso!")
            else:
                st.error("Por favor, preencha o nome do cliente.")