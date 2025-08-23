import streamlit as st
import re
from datetime import datetime
from db.functions import get_mysql_conn  # mesmo padrão usado em adicionar_usuario



# -----------------------------
# Validação de senha (mesmos critérios)
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
# Acesso ao banco
# -----------------------------
def _get_login_by_usuario(usuario: str):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM login WHERE id=%s LIMIT 1", (usuario,))
            return cursor.fetchone()

def _get_psicologo_nome_by_id(pid: int | None):
    if not pid:
        return None
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nome FROM psicologos WHERE id=%s LIMIT 1", (pid,))
            row = cursor.fetchone()
            return row["nome"] if row else None

def _usuario_existe(novo_usuario: str) -> bool:
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM login WHERE usuario=%s LIMIT 1", (novo_usuario,))
            return cursor.fetchone() is not None

def _update_nome_usuario(id_login: int, nome_atual: str, novo_nome: str, funcao: str, psicologo_responsavel: int | None):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            # 1) Atualiza nome no login
            cursor.execute("UPDATE login SET usuario=%s WHERE id=%s", (novo_nome, id_login))

            # 2) Se for Psicóloga, mantemos coerência no cadastro de psicólogos (nome exibição)
            if funcao == "Psicóloga" and psicologo_responsavel:
                cursor.execute("UPDATE psicologos SET nome=%s WHERE id=%s", (novo_nome, psicologo_responsavel))

        conn.commit()

def _update_senha_usuario(id_login: int, senha_nova: str):
    with get_mysql_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE login SET senha=%s WHERE id=%s", (senha_nova, id_login))
        conn.commit()

# -----------------------------
# Página
# -----------------------------
def show_perfil():
    st.title("👤 Meu perfil")

    # Pegamos o usuário logado da sessão
    usuario_atual = st.session_state.get("id_usuario")
    if not usuario_atual:
        st.warning("Faça login para acessar o seu perfil.")
        st.stop()

    row = _get_login_by_usuario(usuario_atual)
    if not row:
        st.error("Não foi possível carregar seu perfil.")
        st.stop()

    # Header com status
    colA, colB, colC = st.columns([2, 1, 1])
    with colA:
        st.subheader(f"Bem-vindo(a), **{row['usuario']}**")
        st.caption(f"Último acesso: {datetime.now():%d %b %Y, %H:%M}")  # opcional; ajuste se tiver audit log
    with colB:
        st.metric("Função", row["funcao"])
    with colC:
        st.metric("Privilégio", "Administrador" if bool(row["privilegio"]) else "Padrão")

    # Detalhes
    with st.expander("📌 Status do usuário", expanded=True):
        nome_resp = _get_psicologo_nome_by_id(row.get("psicologo_responsavel"))
        st.write(
            f"""
            - **Login (usuário):** `{row['usuario']}`
            - **Função:** {row['funcao']}
            - **Psicóloga responsável:** {nome_resp or "—"}
            - **Privilégio:** {"✅ Administrador" if bool(row["privilegio"]) else "❌ Padrão"}
            """
        )

    st.divider()

    # -----------------------------
    # Alterar nome de usuário
    # -----------------------------
    st.subheader("✏️ Alterar nome de usuário")
    with st.form("form_alterar_nome", clear_on_submit=False):
        novo_nome = st.text_input("Novo nome de usuário", value=row["usuario"])
        enviar_nome = st.form_submit_button("Salvar novo nome")

    if enviar_nome:
        novo_nome_limpo = (novo_nome or "").strip()
        if not novo_nome_limpo:
            st.error("Informe um nome válido.")
        elif novo_nome_limpo == row["usuario"]:
            st.info("O novo nome é igual ao atual.")
        elif _usuario_existe(novo_nome_limpo):
            st.error("Já existe um usuário com esse nome.")
        else:
            try:
                _update_nome_usuario(
                    id_login=row["id"],
                    nome_atual=row["usuario"],
                    novo_nome=novo_nome_limpo,
                    funcao=row["funcao"],
                    psicologo_responsavel=row.get("psicologo_responsavel"),
                )
                st.success("✅ Nome atualizado com sucesso.")
                # Atualiza sessão e recarrega
                st.session_state["usuario"] = novo_nome_limpo
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar nome: {e}")

    st.divider()

    # -----------------------------
    # Alterar senha
    # -----------------------------
    st.subheader("🔒 Alterar senha")
    with st.form("form_alterar_senha", clear_on_submit=True):
        senha_atual = st.text_input("Senha atual", type="password")
        senha_nova  = st.text_input("Nova senha", type="password")
        senha_conf  = st.text_input("Confirme a nova senha", type="password")
        enviar_senha = st.form_submit_button("Atualizar senha")

    if enviar_senha:
        # Verifica senha atual (observação: seu schema guarda em texto puro;
        # se passar a hash, ajuste aqui para comparar hash)
        if (senha_atual or "") != (row["senha"] or ""):
            st.error("Senha atual incorreta.")
        elif senha_nova != senha_conf:
            st.error("A confirmação não corresponde à nova senha.")
        else:
            erros = validar_criterios_senha(senha_nova)
            if erros:
                st.warning("A nova senha não atende aos critérios:")
                for e in erros:
                    st.info(e)
            else:
                try:
                    _update_senha_usuario(row["id"], senha_nova)
                    st.success("✅ Senha atualizada com sucesso.")
                except Exception as e:
                    st.error(f"Erro ao atualizar senha: {e}")
