import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import re
import matplotlib.pyplot as plt
import io

# ===========================
# CONFIGURAÇÃO
# ===========================
st.set_page_config(page_title="Controle de Consultas", layout="wide")

USUARIO = "admin"
SENHA = "1234"

# ===========================
# LOGIN
# ===========================
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🔐 Login")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if usuario == USUARIO and senha == SENHA:
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

    st.stop()

# ===========================
# FUNÇÃO CPF
# ===========================
def formatar_cpf(cpf):
    cpf = re.sub(r"\D", "", cpf)[:11]
    if len(cpf) >= 9:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    elif len(cpf) >= 6:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:]}"
    elif len(cpf) >= 3:
        return f"{cpf[:3]}.{cpf[3:]}"
    return cpf

# ===========================
# BANCO DE DADOS
# ===========================
conn = sqlite3.connect("consultas.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS consultas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_paciente TEXT,
    cpf TEXT,
    descricao TEXT,
    valor_pago REAL,
    data_hora TEXT
)
""")
conn.commit()

# ===========================
# MENU
# ===========================
st.sidebar.title("📋 Menu")

pagina = st.sidebar.radio(
    "Selecione:",
    [
        "➕ Adicionar nova consulta",
        "📄 Ver consultas realizadas",
        "📊 Resumo financeiro",
        "🚪 Sair"
    ]
)

if pagina == "🚪 Sair":
    st.session_state.logado = False
    st.rerun()

# ===========================
# ADICIONAR CONSULTA
# ===========================
if pagina == "➕ Adicionar nova consulta":
    st.title("➕ Nova consulta")

    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome do paciente")

        if "cpf" not in st.session_state:
            st.session_state.cpf = ""

        cpf_input = st.text_input("CPF", st.session_state.cpf, max_chars=14)
        st.session_state.cpf = formatar_cpf(cpf_input)

    with col2:
        valor = st.number_input("Valor pago (R$)", min_value=0.0, step=10.0)

    descricao = st.text_area("Descrição da consulta")
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    st.info(f"🕒 Data e hora: {data_hora}")

    if st.button("💾 Salvar consulta"):
        if nome and st.session_state.cpf:
            cursor.execute("""
                INSERT INTO consultas
                (nome_paciente, cpf, descricao, valor_pago, data_hora)
                VALUES (?, ?, ?, ?, ?)
            """, (nome, st.session_state.cpf, descricao, valor, data_hora))
            conn.commit()
            st.success("Consulta salva com sucesso!")
            st.session_state.cpf = ""
        else:
            st.error("Nome e CPF são obrigatórios")

# ===========================
# VER CONSULTAS + EXPORTAR + APAGAR
# ===========================
elif pagina == "📄 Ver consultas realizadas":
    st.title("📄 Consultas realizadas")

    df = pd.read_sql("SELECT * FROM consultas ORDER BY id DESC", conn)

    if df.empty:
        st.warning("Nenhuma consulta registrada.")
    else:
        # EXPORTAR
        buffer = io.BytesIO()
        df.drop(columns=["id"]).to_excel(buffer, index=False)
        st.download_button(
            "📤 Exportar para Excel",
            buffer,
            file_name="consultas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.divider()

        # LIXEIRA
        df["🗑️ Apagar"] = False

        edited_df = st.data_editor(
            df.drop(columns=["id"]),
            use_container_width=True,
            num_rows="fixed"
        )

        if st.button("❌ Confirmar exclusões"):
            ids = df.loc[edited_df["🗑️ Apagar"] == True, "id"]

            if len(ids) == 0:
                st.warning("Nenhuma consulta selecionada.")
            else:
                for i in ids:
                    cursor.execute("DELETE FROM consultas WHERE id = ?", (int(i),))
                conn.commit()
                st.success("Consulta(s) apagada(s)")
                st.rerun()

# ===========================
# RESUMO FINANCEIRO
# ===========================
elif pagina == "📊 Resumo financeiro":
    st.title("📊 Resumo financeiro anual")

    df = pd.read_sql("SELECT valor_pago, data_hora FROM consultas", conn)
    ano = datetime.now().year

    meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    base = pd.DataFrame({"mes": meses, "valor": [0]*12})

    if not df.empty:
        df["data"] = pd.to_datetime(df["data_hora"], dayfirst=True)
        df = df[df["data"].dt.year == ano]
        df["mes"] = df["data"].dt.month - 1

        for _, row in df.iterrows():
            base.loc[row["mes"], "valor"] += row["valor_pago"]

    st.metric("💰 Total no ano", f"R$ {base['valor'].sum():,.2f}")

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(base["mes"], base["valor"])

    ax.set_title(f"Arrecadação mensal - {ano}")
    ax.set_ylabel("Valor (R$)")
    ax.grid(axis="y", linestyle="--", alpha=0.6)

    for bar in bars:
        v = bar.get_height()
        if v > 0:
            ax.text(bar.get_x() + bar.get_width()/2, v, f"R$ {v:,.0f}",
                    ha="center", va="bottom", fontsize=9)

    st.pyplot(fig)
