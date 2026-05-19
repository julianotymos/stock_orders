import streamlit as st
import pandas as pd

from db_config import get_db_connection
from functions_modules.calculate_order import calculate_order_suggestions
from functions_modules.save_order import save_order
from functions_modules.fetch_supplier import fetch_supplier_availability
from functions_modules.read_current_stock import read_empty_positions_count

st.set_page_config(page_title="Gerar Pedido", page_icon="🛒", layout="wide")
st.title("🛒 Gerar Pedido de Reposição")


@st.cache_data(ttl=180)
def load_suggestions(days: int, include_no_position: bool = False):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            suggestions = [dict(r) for r in calculate_order_suggestions(cursor, days, include_no_position)]
            empty = read_empty_positions_count(cursor)
        return suggestions, empty
    finally:
        conn.close()


# Configurações do pedido
with st.expander("⚙️ Parâmetros de análise", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        days = st.selectbox(
            "Período de análise do consumo",
            [7, 15, 21, 30, 60, 90],
            index=2,
            format_func=lambda x: f"{x} dias",
        )
        show_all = st.checkbox("Mostrar todos os produtos (inclusive sem necessidade de reposição)", value=False)
        show_no_position = st.checkbox("Incluir produtos ativos sem posição no freezer", value=False)
    with col2:
        responsible = st.text_input("Responsável pelo pedido", placeholder="Nome do responsável...")
        notes = st.text_area("Observações", placeholder="Observações gerais do pedido...", height=68)

st.divider()

try:
    all_suggestions, empty_positions = load_suggestions(days, show_no_position)

    if not all_suggestions:
        st.warning("Nenhum produto encontrado no estoque.")
        st.stop()

    df_all = pd.DataFrame(all_suggestions)
    df_all['min_para_alvo'] = (df_all['target_qty'] - df_all['closed_qty']).clip(lower=0).astype(int)
    df_all['confirmed_qty'] = df_all['min_para_alvo']
    df_all['supplier_available'] = None
    df_all['supplier_price'] = None

    df_show = df_all if show_all else df_all[df_all['suggested_qty'] > 0]

    needs_order = int((df_all['suggested_qty'] > 0).sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Produtos analisados", len(df_all))
    m2.metric("Precisam reposição", needs_order)
    m3.metric("Caixas fechadas (estoque)", int(df_all['closed_qty'].sum()),
              help="Total de caixas fechadas — base para decisão de pedido")
    m4.metric("Posições vazias", empty_positions,
              help="Posições disponíveis para receber produto")

    st.subheader("Tabela de pedido")
    st.caption(
        "**Caixas fechadas** = estoque disponível para pedido (não abertas ainda). "
        "**Caixas abertas** = em consumo na loja, não contam para o pedido. "
        "Edite a coluna **Qtd Confirmada** conforme necessário."
    )

    if df_show.empty:
        st.success("Todos os produtos estão dentro do estoque mínimo de caixas fechadas.")
    else:
        edited_df = st.data_editor(
            df_show,
            key=f"order_editor_{days}_{show_all}",
            column_config={
                'id':                    None,
                'total_positions':       None,
                'local_desc':            None,
                'open_qty':              None,
                'product_desc':          st.column_config.TextColumn("Produto (The Best)", disabled=True, width="large"),
                'product_type':          st.column_config.TextColumn("Tipo", disabled=True),
                'closed_qty':            st.column_config.NumberColumn(
                                             "Fechadas (estoque)",
                                             disabled=True,
                                             help="Caixas fechadas — base para decisao de pedido"
                                         ),
                'min_qty':               st.column_config.NumberColumn("Minimo (fechadas)", disabled=True),
                'target_qty':            st.column_config.NumberColumn("Alvo (fechadas)", disabled=True),
                'total_consumed':        st.column_config.NumberColumn(f"Consumido ({days}d)", disabled=True),
                'avg_daily_consumption': st.column_config.NumberColumn("Consumo/dia", format="%.2f", disabled=True),
                'avg_platform_30d':      st.column_config.NumberColumn("Média Pedido 30d (The Best)", format="%.2f", disabled=True),
                'min_para_alvo':         st.column_config.NumberColumn("Mín. p/ Alvo", disabled=True,
                                             help="Quantidade mínima para atingir o estoque alvo"),
                'suggested_qty':         st.column_config.NumberColumn("Sugerido", disabled=True),
                'confirmed_qty':         st.column_config.NumberColumn("Qtd Confirmada", min_value=0),
                'supplier_available':    st.column_config.CheckboxColumn("Disponivel Fornec.", disabled=True),
                'supplier_price':        st.column_config.NumberColumn("Preco Fornec.", format="R$ %.2f", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # Verificar fornecedor
        col_sup, col_save = st.columns([1, 1])
        with col_sup:
            if st.button("🔍 Verificar disponibilidade no fornecedor", use_container_width=True):
                product_ids = edited_df['id'].tolist()
                try:
                    with st.spinner("Consultando API do fornecedor..."):
                        result = fetch_supplier_availability(product_ids)

                    if all(v['available'] is None for v in result.values()):
                        st.warning(
                            "SUPPLIER_API_URL não está configurado no .env. "
                            "Configure a URL e chave da API do fornecedor para usar essa funcionalidade."
                        )
                    else:
                        for pid, info in result.items():
                            mask = edited_df['id'] == pid
                            edited_df.loc[mask, 'supplier_available'] = info.get('available')
                            edited_df.loc[mask, 'supplier_price'] = info.get('price')
                        available_count = sum(1 for v in result.values() if v.get('available'))
                        st.success(f"{available_count} de {len(product_ids)} produtos disponíveis no fornecedor.")
                except (TimeoutError, ConnectionError) as e:
                    st.error(str(e))

        with col_save:
            if st.button("💾 Salvar Pedido", type="primary", use_container_width=True):
                items_to_save = edited_df[edited_df['confirmed_qty'] > 0].to_dict('records')

                below_target = [
                    r for r in items_to_save
                    if r['confirmed_qty'] < r['min_para_alvo']
                ]
                if below_target:
                    for r in below_target:
                        st.error(
                            f"**{r['product_desc']}**: confirmado {int(r['confirmed_qty'])} cx — "
                            f"mínimo para atingir alvo é **{int(r['min_para_alvo'])} cx** "
                            f"(alvo {int(r['target_qty'])} − estoque {int(r['closed_qty'])})."
                        )
                elif not items_to_save:
                    st.warning("Nenhum item com quantidade confirmada > 0.")
                elif not responsible.strip():
                    st.warning("Informe o responsável pelo pedido.")
                else:
                    try:
                        conn = get_db_connection()
                        with conn.cursor() as cursor:
                            order_id = save_order(
                                cursor=cursor,
                                period_days=days,
                                notes=notes.strip(),
                                created_by=responsible.strip(),
                                items=items_to_save,
                            )
                            conn.commit()
                        conn.close()
                        st.success(f"Pedido #{order_id} salvo com sucesso! {len(items_to_save)} itens.")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Erro ao salvar pedido: {e}")

except Exception as e:
    st.error(f"Erro ao carregar sugestões: {e}")
