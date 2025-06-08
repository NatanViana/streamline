# /pages/dashboard.py
import streamlit as st
from db.functions import adicionar_usuario, get_proximo_id, listar_psicologos, listar_login_privilegios, atualizar_privilegio_usuario
import re

# validar senha
def senha_valida(senha):
    return (
        len(senha) >= 8 and
        re.search(r"[A-Z]", senha) and
        re.search(r"[a-z]", senha) and
        re.search(r"[0-9]", senha) and
        re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha)
    )

# Função cadastro
def cadastro():
    st.info("📝 Cadastro de Novo Usuário (Necessário Psicólogo Responsável)")
    novo_usuario = st.text_input("Novo Usuário")
    nova_senha = st.text_input("Nova Senha", type="password")
    if not senha_valida(nova_senha):
       st.warning("⚠️ Senha deve obedecer critérios de segurança.")
    funcao = st.selectbox("Função", ['Assistente', 'Psicóloga'])
    if funcao == 'Psicóloga':
        # Gerar novo id incremental
        novo_id = get_proximo_id("psicologos")
        psicologo_responsavel = novo_id
        privilegio = True
    else:
        psicologos = listar_psicologos()
        # Criar dicionário {nome: id}
        psicologos_dict = dict(zip(psicologos['nome'], psicologos['id']))
        # Usar os nomes no selectbox
        nome_selecionado = st.selectbox("Psicólogo Responsável", list(psicologos_dict.keys()))
        # Obter o ID correspxondente ao nome selecionado
        psicologo_responsavel = psicologos_dict[nome_selecionado]
        privilegio = False
    if st.button("Cadastrar Usuário"):
        try:
            if not novo_usuario or not nova_senha or not psicologo_responsavel or not senha_valida(nova_senha):
                st.warning("⚠️ Preencha todos os campos corretamente.")
            else:
                adicionar_usuario(novo_usuario, nova_senha, funcao, psicologo_responsavel, privilegio)
                st.success(f"✅ Usuário {novo_usuario} cadastrado com sucesso!")
                st.info("Agora faça login com o novo usuário.")
        except ValueError as e:
            st.error(f"Erro: {e}")

def conceder_privilegio():
    usuarios = listar_login_privilegios()  # Deve retornar um DataFrame

    if usuarios.empty:
        st.warning("Nenhum usuário cadastrado.")
        return

    # Cria as opções do selectbox com base no DataFrame
    opcoes = [
        f"{row['id']} - {row['login']} (Privilégio: {'✅' if row['privilegio'] else '❌'})"
        for _, row in usuarios.iterrows()
    ]
    usuario_selecionado = st.selectbox("Selecione o usuário", opcoes)

    # Extrai o ID do usuário selecionado
    id_usuario = int(usuario_selecionado.split(" - ")[0])
    
    # Filtra o DataFrame pelo ID selecionado
    usuario_row = usuarios[usuarios['id'] == id_usuario].iloc[0]

    novo_privilegio = st.checkbox(
        "Conceder Privilégio (Administrador)?",
        value=bool(usuario_row['privilegio'])
    )

    if st.button("💾 Atualizar Privilégio"):
        atualizar_privilegio_usuario(id_usuario, novo_privilegio)
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

    