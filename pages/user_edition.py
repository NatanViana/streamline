# /pages/dashboard.py
import streamlit as st
from db.functions import adicionar_usuario, get_proximo_id, listar_psicologos, listar_login_privilegios, atualizar_privilegio_usuario


# Função cadastro
def cadastro():
    st.info("📝 Cadastro de Novo Usuário (Necessário Psicólogo Responsável)")
    novo_usuario = st.text_input("Novo Usuário")
    nova_senha = st.text_input("Nova Senha", type="password")
    funcao = st.selectbox("Função", ['Assistente', 'Psicóloga'])
    if funcao == 'Psicóloga':
        # Gerar novo id incremental
        novo_id = get_proximo_id("psicologos")
        psicologo_responsavel = novo_id
        privilegio = True
    else:
        psicologos = listar_psicologos()
        print(rf"Print psicologos", psicologos)
        # Criar dicionário {nome: id}
        psicologos_dict = {row[1]: row[0] for row in psicologos}
        # Usar os nomes no selectbox
        nome_selecionado = st.selectbox("Psicólogo Responsável", list(psicologos_dict.keys()))
        # Obter o ID correspondente ao nome
        psicologo_responsavel = psicologos_dict[nome_selecionado]
        privilegio = False
    if st.button("Cadastrar Usuário"):
        try:
            if not novo_usuario or not nova_senha or not psicologo_responsavel:
                st.warning("⚠️ Preencha todos os campos.")
            else:
                adicionar_usuario(novo_usuario, nova_senha, funcao, psicologo_responsavel, privilegio)
                st.success(f"✅ Usuário {novo_usuario} cadastrado com sucesso!")
                st.info("Agora faça login com o novo usuário.")
        except ValueError as e:
            st.error(f"Erro: {e}")

# Função de conceder privilégio
def conceder_privilegio():
    usuarios = listar_login_privilegios()

    if not usuarios:
        st.warning("Nenhum usuário cadastrado.")
        return

    opcoes = [f"{row[0]} - {row[1]} (Privilégio: {'✅' if row[2] else '❌'})" for row in usuarios]
    usuario_selecionado = st.selectbox("Selecione o usuário", opcoes)

    id_usuario = int(usuario_selecionado.split(" - ")[0])
    usuario_row = [u for u in usuarios if u[0] == id_usuario][0]

    novo_privilegio = st.checkbox(
        "Conceder Privilégio (Administrador)?",
        value=bool(usuario_row[2])
    )

    if st.button("💾 Atualizar Privilégio"):
        atualizar_privilegio_usuario(id_usuario,novo_privilegio)
        st.success("✅ Privilégio atualizado com sucesso.")
        st.rerun()

def show_edicao_usuarios():
    st.title("📊 Edição de usuários")
    st.write("Configure permissões ou adicione novos usuários")
    click = st.selectbox("Edição de Usuários", ['Novo usuário', 'Conceder privilégios'])
    if click == 'Novo usuário':
        cadastro()
    else:
        conceder_privilegio()

    