import streamlit as st
import pandas as pd

from db_config import get_db_connection
from functions_modules.read_stock_minimum import read_stock_minimum
from functions_modules.upsert_stock_minimum import upsert_stock_minimum

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")
st.title("⚙️ Configurações de Estoque Mínimo")
st.caption(
    "Defina o estoque mínimo e alvo por produto. "
    "O sistema usa esses valores junto com a média de consumo para sugerir pedidos de reposição."
)


@st.cache_data(ttl=60)
def load_config() -> list:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            return [dict(r) for r in read_stock_minimum(cursor)]
    finally:
        conn.close()


try:
    config_rows = load_config()

    if not config_rows:
        st.warning("Nenhum produto encontrado no estoque. Verifique a tabela FREEZER_POSITION.")
        st.stop()

    df = pd.DataFrame(config_rows)

    st.info(
        "**Mínimo:** quantidade de itens abertos abaixo da qual um pedido é gerado.\n\n"
        "**Alvo:** quantidade desejada após reposição.\n\n"
        "**Período (dias):** janela de análise do histórico de consumo para este produto."
    )

    edited = st.data_editor(
        df,
        key="config_editor",
        column_config={
            'product_id':   None,
            'updated_at':   None,
            'product_desc': st.column_config.TextColumn("Produto", disabled=True, width="large"),
            'product_type': st.column_config.TextColumn("Tipo", disabled=True),
            'min_qty':      st.column_config.NumberColumn("Mínimo", min_value=0, step=1),
            'target_qty':   st.column_config.NumberColumn("Alvo", min_value=0, step=1),
            'period_days':  st.column_config.NumberColumn("Período (dias)", min_value=1, max_value=365, step=1),
        },
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    if st.button("💾 Salvar configurações", type="primary", use_container_width=False):
        errors = []
        saved = 0
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                for _, row in edited.iterrows():
                    if row['target_qty'] < row['min_qty']:
                        errors.append(f"{row['product_desc']}: Alvo ({row['target_qty']}) menor que Mínimo ({row['min_qty']}).")
                        continue
                    upsert_stock_minimum(
                        cursor=cursor,
                        product_id=int(row['product_id']),
                        min_qty=int(row['min_qty']),
                        target_qty=int(row['target_qty']),
                        period_days=int(row['period_days']),
                    )
                    saved += 1
                conn.commit()
            conn.close()
            st.cache_data.clear()

            if errors:
                for err in errors:
                    st.warning(err)
            if saved:
                st.success(f"{saved} produto(s) configurado(s) com sucesso.")

        except Exception as e:
            st.error(f"Erro ao salvar configurações: {e}")

except Exception as e:
    st.error(f"Erro ao carregar configurações: {e}")
