# /pages/dashboard.py
import streamlit as st
from db.functions import (
    adicionar_usuario,
    get_proximo_id,
    listar_psicologos,
    listar_login_privilegios,
    atualizar_privilegio_usuario,
)
import re
import pandas as pd

# -----------------------------
# Validação de senha
# -----------------------------
def validar_criterios_senha(senha: str):
    erros = []
    if len(senha or "") < 8:
        erros.append("🔒 Mínimo de 8 caracteres")
    if not re.search(r"[A-Z]", senha or ""):
        erros.append("🔒 Pelo menos uma letra maiúscula (A-Z)")
    if not re.search(r"[a-z]", senha or ""):
        erros.append("🔒 Pelo menos uma letra minúscula (a-z)")
    if not re.search(r"[0-9]", senha or ""):
        erros.append("🔒 Pelo menos um número (0-9)")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha or ""):
        erros.append("🔒 Pelo menos um caractere especial (!@#$...)")
    return erros

# -----------------------------
# Abas / Páginas
# -----------------------------
def aba_novo_usuario():
    st.subheader("📝 Cadastro de Novo Usuário")

    # 1) Fora do form para permitir rerun dinâmico
    funcao = st.selectbox("Função", ["Assistente", "Psicóloga"], key="novo_user_funcao")

    privilegio = 0
    psicologo_responsavel = None

    # 2) Dentro do form ficam os campos que serão enviados
    with st.form("form_novo_usuario", clear_on_submit=False):
        novo_usuario = st.text_input("Novo Usuário", key="novo_user_nome")

        if funcao == "Assistente":
            psicologos_df = listar_psicologos()
            if psicologos_df.empty:
                st.warning("⚠️ Cadastre pelo menos uma Psicóloga antes de criar Assistentes.")
            else:
                psicologos_dict = dict(zip(psicologos_df["nome"], psicologos_df["id"]))
                nome_sel = st.selectbox(
                    "Psicóloga Responsável",
                    list(psicologos_dict.keys()),
                    key="novo_user_resp"
                )
                psicologo_responsavel = psicologos_dict[nome_sel]
        else:
            st.info("Ao criar uma Psicóloga, ela será definida automaticamente como responsável por si mesma.")

        nova_senha = st.text_input("Nova Senha", type="password", key="novo_user_senha")
        submitted = st.form_submit_button("Cadastrar Usuário")

    # Feedback e submit
    if nova_senha:
        erros = validar_criterios_senha(nova_senha)
        if erros:
            st.warning("⚠️ A senha não atende aos seguintes critérios:")
            for e in erros:
                st.info(e)
        else:
            st.success("✅ A senha atende a todos os critérios de segurança.")

    if submitted:
        erros = validar_criterios_senha(nova_senha)
        campos_ok = (
            novo_usuario
            and nova_senha
            and (funcao != "Assistente" or psicologo_responsavel)  # exige responsável só p/ assistente
            and not erros
        )

        if not campos_ok:
            st.warning("⚠️ Preencha todos os campos corretamente e corrija a senha.")
            return

        try:
            resp = psicologo_responsavel if funcao == "Assistente" else None
            adicionar_usuario(novo_usuario, nova_senha, funcao, resp, privilegio)
            st.success(f"✅ Usuário {novo_usuario} cadastrado com sucesso!")
            st.info("Agora faça login com o novo usuário.")
        except ValueError as e:
            st.error(f"Erro: {e}")

def aba_promover_psicologa():
    st.subheader("⬆️ Promover Assistente para Psicóloga")

    usuarios = listar_login_privilegios()
    if usuarios.empty:
        st.info("Nenhum usuário cadastrado.")
        return

    candidatos = usuarios[usuarios["funcao"] != "Psicóloga"].copy()
    if candidatos.empty:
        st.info("Todos os usuários já são Psicólogas.")
        return

    nomes = candidatos["usuario"].tolist()

    with st.form("form_promover", clear_on_submit=False):
        usuario_sel = st.selectbox("Usuário", nomes)
        submitted = st.form_submit_button("Promover")

    if submitted:
        # placeholder só para cumprir a assinatura (o backend deve ignorar e usar o próprio id)
        psicologo_responsavel_placeholder = get_proximo_id("psicologos")
        try:
            adicionar_usuario(usuario_sel, None, "Psicóloga", psicologo_responsavel_placeholder, True)
            st.success(f"✅ {usuario_sel} promovido(a) para Psicóloga com sucesso.")
            st.rerun()
        except ValueError as e:
            st.error(f"Erro ao promover: {e}")

def aba_conceder_privilegios():
    st.subheader("🔐 Conceder privilégios")
    usuarios = listar_login_privilegios()

    if usuarios.empty:
        st.warning("Nenhum usuário cadastrado.")
        return

    # Garantir colunas esperadas
    if not set(["id", "usuario", "privilegio"]).issubset(usuarios.columns):
        # Se veio sem colunas ou colunas com nomes diferentes, evita quebra visual
        usuarios = usuarios.rename(columns={
            "user_id": "id",
            "nome": "usuario",
            "is_admin": "privilegio",
        })

    opcoes = [
        f"{row['id']} - {row['usuario']} (Privilégio: {'✅' if bool(row['privilegio']) else '❌'})"
        for _, row in usuarios.iterrows()
    ]
    usuario_selecionado = st.selectbox("Selecione o usuário", opcoes)

    # Extrai o ID
    try:
        id_usuario = int(usuario_selecionado.split(" - ")[0])
    except Exception:
        st.error("Falha ao identificar o usuário selecionado.")
        return

    # Linha do usuário
    try:
        usuario_row = usuarios[usuarios["id"] == id_usuario].iloc[0]
    except IndexError:
        st.error("Usuário não encontrado na lista.")
        return

    novo_privilegio = st.checkbox(
        "Conceder Privilégio (Administrador)?",
        value=bool(usuario_row["privilegio"]),
    )

    if st.button("💾 Atualizar Privilégio"):
        try:
            atualizar_privilegio_usuario(id_usuario, novo_privilegio)
            st.success("✅ Privilégio atualizado com sucesso.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao atualizar privilégio: {e}")

# -----------------------------
# Entrada principal
# -----------------------------
def show_edicao_usuarios():
    st.title("📊 Edição de usuários")
    st.write("Configure permissões, promova funções ou adicione novos usuários.")

    tab1, tab2, tab3 = st.tabs(["🆕 Novo usuário", "⬆️ Promover para Psicóloga", "🔐 Privilégios"])
    with tab1:
        aba_novo_usuario()
    with tab2:
        aba_promover_psicologa()
    with tab3:
        aba_conceder_privilegios()
