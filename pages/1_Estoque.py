import streamlit as st
import pandas as pd
import plotly.express as px

from db_config import get_db_connection
from functions_modules.read_current_stock import read_current_stock, read_empty_positions_count
from functions_modules.read_consumption import read_consumption_summary, read_consumption_over_time

st.set_page_config(page_title="Estoque", page_icon="📊", layout="wide")
st.title("📊 Estoque Atual")


@st.cache_data(ttl=120)
def load_stock():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            stock = [dict(r) for r in read_current_stock(cursor)]
            empty = read_empty_positions_count(cursor)
        return stock, empty
    finally:
        conn.close()


@st.cache_data(ttl=120)
def load_consumption(days: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            summary = [dict(r) for r in read_consumption_summary(cursor, days)]
            over_time = [dict(r) for r in read_consumption_over_time(cursor, days)]
        return summary, over_time
    finally:
        conn.close()


# Filtros
col_search, col_days = st.columns([3, 1])
with col_search:
    search = st.text_input("Buscar produto", placeholder="Digite parte do nome...")
with col_days:
    days = st.selectbox("Período de consumo", [7, 15, 30, 60, 90], index=2, format_func=lambda x: f"{x} dias")

try:
    stock_rows, empty_positions = load_stock()
    consumption_rows, over_time_rows = load_consumption(days)

    df_stock = pd.DataFrame(stock_rows)
    df_consumption = pd.DataFrame(consumption_rows)
    df_time = pd.DataFrame(over_time_rows)

    if search and not df_stock.empty:
        mask = df_stock['product_desc'].str.contains(search, case=False, na=False)
        df_stock = df_stock[mask]

    # Métricas
    st.subheader("Resumo")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Produtos no estoque", df_stock['id'].nunique() if not df_stock.empty else 0)
    m2.metric("Posições abertas", int(df_stock['open_qty'].sum()) if not df_stock.empty else 0)
    m3.metric("Posições fechadas", int(df_stock['closed_qty'].sum()) if not df_stock.empty else 0)
    m4.metric("Posições vazias", empty_positions, help="Posições disponíveis para receber produto")
    m5.metric(
        f"Consumidos ({days}d)",
        int(df_consumption['total_consumed'].sum()) if not df_consumption.empty else 0
    )

    st.divider()

    # Tabela de estoque
    st.subheader("Estoque por produto e freezer")
    if not df_stock.empty:
        display = df_stock.rename(columns={
            'product_desc':    'Produto',
            'product_type':    'Tipo',
            'freezer_name':    'Freezer',
            'open_qty':        'Abertos',
            'closed_qty':      'Fechados',
            'total_positions': 'Total',
            'last_update':     'Última atualização',
        })[['Produto', 'Tipo', 'Freezer', 'Abertos', 'Fechados', 'Total', 'Última atualização']]
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto encontrado com esse filtro.")

    st.divider()

    # Gráfico de consumo por produto
    st.subheader(f"Top 15 produtos mais consumidos — últimos {days} dias")
    if not df_consumption.empty:
        top15 = df_consumption.head(15)
        fig_bar = px.bar(
            top15,
            x='product_desc',
            y='total_consumed',
            color='product_type',
            labels={
                'product_desc':   'Produto',
                'total_consumed': 'Unidades consumidas',
                'product_type':   'Tipo',
            },
        )
        fig_bar.update_layout(xaxis_tickangle=-40, showlegend=True)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info(f"Sem histórico de consumo nos últimos {days} dias.")

    # Gráfico de consumo ao longo do tempo
    if not df_time.empty:
        st.subheader(f"Consumo por semana — últimos {days} dias")
        top_products = df_consumption.head(8)['product_desc'].tolist()
        df_time_filtered = df_time[df_time['product_desc'].isin(top_products)]
        fig_line = px.line(
            df_time_filtered,
            x='week',
            y='consumed',
            color='product_desc',
            markers=True,
            labels={'week': 'Semana', 'consumed': 'Consumido', 'product_desc': 'Produto'},
        )
        st.plotly_chart(fig_line, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
