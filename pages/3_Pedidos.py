import streamlit as st
import pandas as pd

from db_config import get_db_connection
from functions_modules.read_orders import read_orders, read_order_items, update_order_status

st.set_page_config(page_title="Pedidos", page_icon="📋", layout="wide")
st.title("📋 Histórico de Pedidos")

STATUS_OPTIONS = ["Todos", "RASCUNHO", "CONFIRMADO", "ENVIADO", "RECEBIDO"]
STATUS_COLORS = {
    "RASCUNHO":   "🟡",
    "CONFIRMADO": "🔵",
    "ENVIADO":    "🟠",
    "RECEBIDO":   "🟢",
}


@st.cache_data(ttl=60)
def load_orders(status_filter: str) -> list:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            status = None if status_filter == "Todos" else status_filter
            return [dict(r) for r in read_orders(cursor, status)]
    finally:
        conn.close()


@st.cache_data(ttl=60)
def load_order_items(order_id: int) -> list:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            return [dict(r) for r in read_order_items(cursor, order_id)]
    finally:
        conn.close()


# Filtros
col_status, col_refresh = st.columns([2, 1])
with col_status:
    status_filter = st.selectbox("Filtrar por status", STATUS_OPTIONS)
with col_refresh:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    orders = load_orders(status_filter)

    if not orders:
        st.info("Nenhum pedido encontrado.")
        st.stop()

    df_orders = pd.DataFrame(orders)

    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("Total de pedidos", len(df_orders))
    m2.metric("Total de itens", int(df_orders['total_items'].sum()))
    m3.metric("Total de unidades confirmadas", int(df_orders['total_qty'].sum()))

    st.divider()

    # Lista de pedidos
    for _, row in df_orders.iterrows():
        icon = STATUS_COLORS.get(row['status'], "⚪")
        order_date = pd.to_datetime(row['order_date']).strftime('%d/%m/%Y %H:%M') if row['order_date'] else "—"

        with st.expander(
            f"{icon} Pedido #{row['id']} — {order_date} | {row['status']} | "
            f"{row['total_items']} produtos | {row['total_qty']} unidades"
        ):
            col_info, col_action = st.columns([3, 1])

            with col_info:
                st.markdown(f"**Responsável:** {row['created_by'] or '—'}")
                st.markdown(f"**Período de análise:** {row['period_days']} dias")
                if row['notes']:
                    st.markdown(f"**Observações:** {row['notes']}")

            with col_action:
                next_statuses = {
                    "RASCUNHO":   ["CONFIRMADO"],
                    "CONFIRMADO": ["ENVIADO", "RASCUNHO"],
                    "ENVIADO":    ["RECEBIDO", "CONFIRMADO"],
                    "RECEBIDO":   [],
                }
                options = next_statuses.get(row['status'], [])
                if options:
                    new_status = st.selectbox(
                        "Alterar status",
                        options,
                        key=f"status_{row['id']}",
                        label_visibility="collapsed",
                    )
                    if st.button("Atualizar", key=f"btn_{row['id']}", use_container_width=True):
                        try:
                            conn = get_db_connection()
                            with conn.cursor() as cursor:
                                update_order_status(cursor, row['id'], new_status)
                                conn.commit()
                            conn.close()
                            st.cache_data.clear()
                            st.success(f"Status atualizado para {new_status}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar status: {e}")
                else:
                    st.success("Pedido finalizado.")

            # Itens do pedido
            items = load_order_items(row['id'])
            if items:
                df_items = pd.DataFrame(items).rename(columns={
                    'product_desc':          'Produto',
                    'product_type':          'Tipo',
                    'current_stock':         'Estoque',
                    'min_qty':               'Mínimo',
                    'avg_daily_consumption': 'Cons./dia',
                    'suggested_qty':         'Sugerido',
                    'confirmed_qty':         'Confirmado',
                    'supplier_available':    'Disponível',
                    'supplier_price':        'Preço (R$)',
                    'notes':                 'Obs',
                })
                cols_show = ['Produto', 'Tipo', 'Estoque', 'Mínimo', 'Cons./dia', 'Sugerido', 'Confirmado', 'Disponível', 'Preço (R$)']
                st.dataframe(df_items[cols_show], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao carregar pedidos: {e}")
