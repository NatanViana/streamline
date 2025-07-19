# /pages/dashboard.py
import streamlit as st
from db.functions import adicionar_usuario, get_proximo_id, listar_psicologos, listar_login_privilegios, atualizar_privilegio_usuario
import re

# Função de validação com retorno detalhado
def validar_criterios_senha(senha):
    erros = []
    if len(senha) < 8:
        erros.append("🔒 Mínimo de 8 caracteres")
    if not re.search(r"[A-Z]", senha):
        erros.append("🔒 Pelo menos uma letra maiúscula (A-Z)")
    if not re.search(r"[a-z]", senha):
        erros.append("🔒 Pelo menos uma letra minúscula (a-z)")
    if not re.search(r"[0-9]", senha):
        erros.append("🔒 Pelo menos um número (0-9)")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha):
        erros.append("🔒 Pelo menos um caractere especial (!@#$...)")
    return erros

# Função de cadastro com feedback por critério
def cadastro():
    st.info("📝 Cadastro de Novo Usuário (Necessário Psicólogo Responsável)")
    novo_usuario = st.text_input("Novo Usuário")
    nova_senha = st.text_input("Nova Senha", type="password")

    erros_senha = validar_criterios_senha(nova_senha)

    if nova_senha:
        if erros_senha:
            st.warning("⚠️ A senha não atende aos seguintes critérios:")
            for erro in erros_senha:
                st.info(erro)
        else:
            st.success("✅ A senha atende a todos os critérios de segurança.")

    funcao = st.selectbox("Função", ['Assistente', 'Psicóloga'])
    if funcao == 'Psicóloga':
        novo_id = get_proximo_id("psicologos")
        psicologo_responsavel = novo_id
        privilegio = True
    else:
        psicologos = listar_psicologos()
        psicologos_dict = dict(zip(psicologos['nome'], psicologos['id']))
        nome_selecionado = st.selectbox("Psicólogo Responsável", list(psicologos_dict.keys()))
        psicologo_responsavel = psicologos_dict[nome_selecionado]
        privilegio = False

    if st.button("Cadastrar Usuário"):
        if not novo_usuario or not nova_senha or not psicologo_responsavel or erros_senha:
            st.warning("⚠️ Preencha todos os campos corretamente e corrija a senha.")
        else:
            try:
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
        f"{row['id']} - {row['usuario']} (Privilégio: {'✅' if row['privilegio'] else '❌'})"
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

    