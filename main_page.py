import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Dashboard de Clientes", layout="wide")

st.title("📊 Dashboard de Acompanhamento de Clientes")

st.sidebar.header("🔐 Login")

user = st.sidebar.text_input("Usuário")
password = st.sidebar.text_input("Senha", type="password")

if user == "cliente1" and password == "senha123":
    st.success("Acesso autorizado!")

    # Dados iniciais (pode ser substituído por upload ou leitura de arquivo)
    if 'df' not in st.session_state:
        dados_csv = """Cliente,Sessoes_Mes,Valor_Pago,Valor_Pendente
    Joao,5,500,100
    Maria,3,300,200
    Pedro,4,400,0
    """
        st.session_state.df = pd.read_csv(StringIO(dados_csv))

    # Sidebar: adicionar ou editar cliente
    st.sidebar.header("🔧 Atualizar Dados")
    with st.sidebar.form("form_client"):
        cliente = st.text_input("Nome do Cliente")
        sessoes = st.number_input("Nº de Sessões no Mês", min_value=0, step=1)
        pago = st.number_input("Valor Pago", min_value=0.0, step=50.0)
        pendente = st.number_input("Valor Pendente", min_value=0.0, step=50.0)
        submitted = st.form_submit_button("Salvar/Atualizar")

        if submitted:
            df = st.session_state.df
            if cliente in df['Cliente'].values:
                st.success(f"Atualizando dados de {cliente}")
                st.session_state.df.loc[df['Cliente'] == cliente, ['Sessoes_Mes', 'Valor_Pago', 'Valor_Pendente']] = [sessoes, pago, pendente]
            else:
                st.success(f"Adicionando novo cliente: {cliente}")
                novo = pd.DataFrame([[cliente, sessoes, pago, pendente]], columns=df.columns)
                st.session_state.df = pd.concat([df, novo], ignore_index=True)

    # Filtro por cliente
    clientes = ["Todos"] + st.session_state.df['Cliente'].tolist()
    cliente_selecionado = st.selectbox("Selecione um cliente", clientes)

    # Dados filtrados
    df = st.session_state.df
    if cliente_selecionado != "Todos":
        df = df[df['Cliente'] == cliente_selecionado]

    # KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Sessões", int(df['Sessoes_Mes'].sum()))
    col2.metric("Valor Pago (R$)", f"{df['Valor_Pago'].sum():.2f}")
    col3.metric("Valor Pendente (R$)", f"{df['Valor_Pendente'].sum():.2f}")

    # Tabela
    st.subheader("📋 Dados dos Clientes")
    st.dataframe(df.reset_index(drop=True), use_container_width=True)

    # Opção para baixar CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar dados como CSV", csv, "dados_clientes.csv", "text/csv")

else:
    st.warning("Acesso negado.")
    st.stop()

