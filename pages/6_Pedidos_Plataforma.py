import streamlit as st
import pandas as pd

from db_config import get_db_connection
from functions_modules.fetch_platform_orders import fetch_all_platform_orders, extract_products_from_orders
from functions_modules.save_supplier_order import save_supplier_orders
from functions_modules.read_supplier_orders import read_supplier_orders, read_supplier_order_items, read_unmapped_products, read_items_for_price_avg, read_item_frequency
from functions_modules.manage_product_mapping import (
    read_product_mapping, upsert_product_mapping, sync_mapping_to_order_items, read_local_products
)

st.set_page_config(page_title="Pedidos Plataforma", page_icon="🏪", layout="wide")
st.title("🏪 Pedidos da Plataforma The Best")

# Garante que as tabelas existem mesmo sem passar pela home
try:
    _conn = get_db_connection()
    with _conn.cursor() as _cur:
        _cur.execute("""
            CREATE TABLE IF NOT EXISTS PRODUCT_MAPPING (
                external_product_id  INT          NOT NULL,
                external_name        VARCHAR(200) NOT NULL,
                local_product_id     INT          REFERENCES PRODUCT(ID),
                updated_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT pk_product_mapping PRIMARY KEY (external_product_id)
            )
        """)
        _cur.execute("""
            CREATE TABLE IF NOT EXISTS SUPPLIER_ORDER (
                id                SERIAL PRIMARY KEY,
                platform_order_id INT          NOT NULL,
                store_id          INT,
                platform_status   INT,
                total             NUMERIC(12,2),
                franchise_tax     NUMERIC(12,2),
                loaded_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_supplier_order_platform UNIQUE (platform_order_id)
            )
        """)
        _cur.execute("ALTER TABLE SUPPLIER_ORDER ADD COLUMN IF NOT EXISTS service_note VARCHAR(100)")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER ADD COLUMN IF NOT EXISTS vhsys INT")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER ADD COLUMN IF NOT EXISTS product_invoice_value NUMERIC(12,2)")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER ADD COLUMN IF NOT EXISTS product_invoice_doc VARCHAR(30)")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER ADD COLUMN IF NOT EXISTS service_invoice_value NUMERIC(12,2)")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER ADD COLUMN IF NOT EXISTS service_invoice_doc VARCHAR(30)")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER_ITEM ADD COLUMN IF NOT EXISTS nfe_bling_id BIGINT")
        _cur.execute("ALTER TABLE SUPPLIER_ORDER_ITEM ADD COLUMN IF NOT EXISTS sale_order_bling_id BIGINT")
        _cur.execute("""
            CREATE TABLE IF NOT EXISTS SUPPLIER_ORDER_ITEM (
                id                    SERIAL PRIMARY KEY,
                order_id              INT          NOT NULL REFERENCES SUPPLIER_ORDER(id) ON DELETE CASCADE,
                platform_item_id      INT,
                external_product_id   INT,
                external_product_name VARCHAR(200),
                external_category     VARCHAR(100),
                quantity              NUMERIC(10,3),
                price_unit            NUMERIC(10,2),
                local_product_id      INT          REFERENCES PRODUCT(ID),
                created_at            TIMESTAMP
            )
        """)
        _conn.commit()
    _conn.close()
except Exception as _e:
    st.error(f"Erro ao verificar tabelas: {_e}")
    st.stop()

tab_load, tab_map, tab_orders, tab_avg, tab_freq = st.tabs(["📥 Carregar Pedidos", "🔗 Normalização de Produtos", "📋 Pedidos Salvos", "📊 Preço Médio", "📈 Análise de Itens"])


# ── TAB 1: Carregar pedidos ─────────────────────────────────────────────────
with tab_load:
    st.subheader("Importar pedidos da plataforma")

    max_pages = st.number_input("Máximo de páginas (50 pedidos/pág)", min_value=1, max_value=20, value=5)

    col_imp, col_upd = st.columns(2)

    with col_imp:
        st.caption("Novos pedidos são adicionados. Pedidos já existentes são ignorados.")
        if st.button("📥 Importar novos pedidos", type="primary", use_container_width=True):
            try:
                with st.spinner("Consultando API da plataforma..."):
                    orders = fetch_all_platform_orders(max_pages=max_pages)
                if not orders:
                    st.warning("Nenhum pedido retornado pela API.")
                else:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        result = save_supplier_orders(cursor, orders, update_existing=False)
                        conn.commit()
                    conn.close()
                    st.success(
                        f"**{result['inserted']}** novos pedidos importados, "
                        f"**{result['skipped']}** já existiam."
                    )
                    st.cache_data.clear()
            except ValueError as e:
                st.error(str(e))
                st.info("Configure PLATFORM_TOKEN no arquivo .env")
            except Exception as e:
                st.error(f"Erro ao importar: {e}")

    with col_upd:
        st.caption("Atualiza status, total e nota fiscal dos pedidos já importados.")
        if st.button("🔄 Atualizar pedidos existentes", use_container_width=True):
            try:
                with st.spinner("Consultando API e atualizando..."):
                    orders = fetch_all_platform_orders(max_pages=max_pages)
                if not orders:
                    st.warning("Nenhum pedido retornado pela API.")
                else:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        result = save_supplier_orders(cursor, orders, update_existing=True)
                        conn.commit()
                    conn.close()
                    st.success(
                        f"**{result['inserted']}** novos, "
                        f"**{result['updated']}** atualizados, "
                        f"**{result['skipped']}** sem alteração."
                    )
                    st.cache_data.clear()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")

    st.divider()
    st.subheader("Pré-visualizar pedidos da API (sem salvar)")
    if st.button("👁 Visualizar pedidos da API", use_container_width=True):
        try:
            with st.spinner("Consultando API..."):
                orders = fetch_all_platform_orders(max_pages=2)
            if orders:
                rows = []
                for o in orders:
                    for item in o.get("orderItems", []):
                        prod = item.get("products") or {}
                        cat = prod.get("category") or {}
                        rows.append({
                            "Pedido ID": o.get("id"),
                            "Status": o.get("status"),
                            "Total": o.get("total"),
                            "Produto ID": item.get("product_id"),
                            "Produto": prod.get("name", ""),
                            "Categoria": cat.get("name", ""),
                            "Qtd": item.get("quantity"),
                            "Preço Unit.": item.get("price_unit"),
                            "Data": item.get("created_at"),
                        })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.warning("Sem dados.")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Erro: {e}")


# ── TAB 2: Normalização ──────────────────────────────────────────────────────
with tab_map:
    st.subheader("Mapear produtos externos para produtos locais")
    st.caption(
        "Associe produtos das categorias **sorvetes** e **acai** da plataforma aos produtos locais do estoque. "
        "Outras categorias (congelados, potes etc.) ficam como estão no pedido e não precisam de mapeamento."
    )

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            mappings = [dict(r) for r in read_product_mapping(cursor)]
            local_products = [dict(r) for r in read_local_products(cursor)]
            unmapped = [dict(r) for r in read_unmapped_products(cursor)]
        conn.close()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

    local_options = {
        (r['description'] if r['status'] == 1 else f"{r['description']} (inativo)"): r['id']
        for r in local_products
    }
    local_names = ["(não mapeado)"] + list(local_options.keys())

    if unmapped:
        st.warning(f"{len(unmapped)} produto(s) nos pedidos ainda sem mapeamento.")
        with st.expander("Mapear produtos pendentes", expanded=True):
            for row in unmapped:
                ext_id = row['external_product_id']
                ext_name = row['external_product_name']
                ext_cat = row['external_category']
                col_name, col_select, col_btn = st.columns([3, 3, 1])
                with col_name:
                    st.markdown(f"**{ext_name}** *(cat: {ext_cat}, id: {ext_id})*")
                with col_select:
                    selected = st.selectbox(
                        "Produto local",
                        local_names,
                        key=f"map_{ext_id}",
                        label_visibility="collapsed",
                    )
                with col_btn:
                    if st.button("Salvar", key=f"save_map_{ext_id}"):
                        local_id = local_options.get(selected) if selected != "(não mapeado)" else None
                        try:
                            conn = get_db_connection()
                            with conn.cursor() as cursor:
                                upsert_product_mapping(cursor, ext_id, ext_name, local_id)
                                conn.commit()
                            conn.close()
                            st.success("Mapeamento salvo.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
    else:
        st.success("Todos os produtos dos pedidos salvos estão mapeados.")

    st.divider()
    st.subheader("Todos os mapeamentos")
    if mappings:
        df_map = pd.DataFrame(mappings)
        df_map.columns = ["ID Externo", "Nome Externo", "ID Local", "Produto Local"]
        st.dataframe(df_map, use_container_width=True, hide_index=True)

        if st.button("Sincronizar mapeamentos nos itens de pedidos", use_container_width=True):
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    updated = sync_mapping_to_order_items(cursor)
                    conn.commit()
                conn.close()
                st.success(f"{updated} item(ns) atualizados com produto local.")
            except Exception as e:
                st.error(f"Erro: {e}")
    else:
        st.info("Nenhum mapeamento cadastrado ainda. Importe pedidos primeiro.")


# ── TAB 3: Pedidos salvos ────────────────────────────────────────────────────
with tab_orders:
    st.subheader("Pedidos importados da plataforma")

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            orders_saved = [dict(r) for r in read_supplier_orders(cursor)]
        conn.close()
    except Exception as e:
        st.error(f"Erro ao carregar pedidos: {e}")
        st.stop()

    if not orders_saved:
        st.info("Nenhum pedido importado ainda. Use a aba **Carregar Pedidos**.")
    else:
        from datetime import date, timedelta
        _df_all = pd.DataFrame(orders_saved)
        _min_date = pd.to_datetime(_df_all['order_date'], errors='coerce').min()
        _min_date = _min_date.date() if pd.notna(_min_date) else date.today() - timedelta(days=365)

        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            filter_start = st.date_input("De", value=_min_date, key="orders_filter_start")
        with col_f2:
            filter_end = st.date_input("Até", value=date.today(), key="orders_filter_end")
        with col_f3:
            filter_pedido = st.text_input("Nº do Pedido", placeholder="Ex: 12345", key="orders_filter_pedido")

        orders_saved = [
            r for r in orders_saved
            if (r.get('order_date') is None or (filter_start <= r['order_date'].date() <= filter_end))
            and (not filter_pedido.strip() or str(r.get('vhsys', '') or '').startswith(filter_pedido.strip()))
        ]

        STATUS_MAP = {
            1: "Confirmado",
            2: "Em trânsito",
            3: "Finalizado",
            5: "Em estoque",
            7: "Em Separação",
        }

        df_orders = pd.DataFrame(orders_saved)
        df_orders['status_desc'] = df_orders['platform_status'].map(STATUS_MAP).fillna(df_orders['platform_status'].astype(str))
        df_orders['alerta'] = df_orders['unmapped_items'].apply(lambda x: f"⚠ {x} sem mapa" if x > 0 else "")

        df_orders['valor_faturado'] = (
            df_orders['product_invoice_value'].fillna(0) +
            df_orders['service_invoice_value'].fillna(0)
        ).replace(0, None)

        _cutoff = pd.Timestamp('2025-06-15')
        _order_dt = pd.to_datetime(df_orders['order_date'], errors='coerce')
        _factor = _order_dt.ge(_cutoff).map({True: 0.85 * 0.06, False: 0.06})
        _piv = pd.to_numeric(df_orders['items_value'], errors='coerce')
        _vf  = pd.to_numeric(df_orders['valor_faturado'], errors='coerce')

        _has_vf = _vf.notna()
        df_orders['dif_icms']      = (_piv * _factor).where(_piv.notna() & _has_vf, other=None)
        df_orders['frete_imposto'] = (_vf - _piv).where(_has_vf & _piv.notna(), other=None)

        _fi_n   = pd.to_numeric(df_orders['frete_imposto'], errors='coerce')
        _icms_n = pd.to_numeric(df_orders['dif_icms'],      errors='coerce')
        df_orders['preco_real'] = (_vf + _fi_n + _icms_n).where(_has_vf, other=None)

        _sel_id = st.session_state.get('detail_order_id')
        df_orders['detalhar'] = df_orders['id'].apply(lambda x: x == _sel_id if _sel_id is not None else False)

        df_display = df_orders.drop(columns=[
            'franchise_tax', 'store_id', 'platform_order_id',
            'product_invoice_doc', 'service_invoice_doc',
            'unmapped_items', 'platform_status', 'total',
        ], errors='ignore').rename(columns={
            'vhsys':                'Pedido',
            'status_desc':          'Status',
            'order_date':           'Data do Pedido',
            'total_items':          'Itens',
            'total_qty':            'Qtd Total',
            'items_value':          'Valor Produtos (R$)',
            'product_invoice_value':'NF Produtos (R$)',
            'service_invoice_value':'NF Serviço (R$)',
            'valor_faturado':       'Valor Faturado (R$)',
            'dif_icms':             'Dif. ICMS (R$)',
            'frete_imposto':        'Frete + Imposto',
            'preco_real':           'Preço Real',
            'alerta':               'Alerta',
            'loaded_at':            'Importado em',
        })

        ordered_cols = [
            'detalhar', 'Pedido', 'Status', 'Data do Pedido',
            'Itens', 'Qtd Total', 'Valor Produtos (R$)',
            'NF Produtos (R$)', 'NF Serviço (R$)', 'Valor Faturado (R$)',
            'Frete + Imposto', 'Dif. ICMS (R$)', 'Preço Real', 'Alerta', 'Importado em', 'id',
        ]
        df_display = df_display[[c for c in ordered_cols if c in df_display.columns]]

        edited = st.data_editor(
            df_display,
            key="orders_editor",
            column_config={
                'id':               None,
                'detalhar':         st.column_config.CheckboxColumn("Detalhar", width="small"),
                'Pedido':           st.column_config.NumberColumn("Pedido", disabled=True),
                'Status':           st.column_config.TextColumn("Status", disabled=True),
                'Data do Pedido':   st.column_config.DatetimeColumn("Data do Pedido", disabled=True, format="DD/MM/YYYY"),
                'Itens':            st.column_config.NumberColumn("Itens", disabled=True),
                'Qtd Total':        st.column_config.NumberColumn("Qtd Total", disabled=True),
                'Dif. ICMS (R$)':   st.column_config.NumberColumn("Dif. ICMS (R$)", disabled=True, format="R$ %.2f"),
                'Valor Produtos (R$)': st.column_config.NumberColumn("Valor Produtos (R$)", disabled=True, format="R$ %.2f"),
                'NF Produtos (R$)': st.column_config.NumberColumn("NF Produtos (R$)", disabled=True, format="R$ %.2f"),
                'NF Serviço (R$)':  st.column_config.NumberColumn("NF Serviço (R$)", disabled=True, format="R$ %.2f"),
                'Valor Faturado (R$)': st.column_config.NumberColumn("Valor Faturado (R$)", disabled=True, format="R$ %.2f"),
                'Frete + Imposto':  st.column_config.NumberColumn("Frete + Imposto", disabled=True, format="R$ %.2f"),
                'Preço Real':       st.column_config.NumberColumn("Preço Real",      disabled=True, format="R$ %.2f"),
                'Alerta':           st.column_config.TextColumn("Alerta", disabled=True),
                'Importado em':     st.column_config.DatetimeColumn("Importado em", disabled=True, format="DD/MM/YYYY"),
            },
            hide_index=True,
            use_container_width=True,
        )

        checked_rows = edited[edited['detalhar'] == True]
        if len(checked_rows) > 1:
            prev_id = st.session_state.get('detail_order_id')
            new_ones = checked_rows[checked_rows['id'] != prev_id]
            new_id = int(new_ones.iloc[0]['id']) if not new_ones.empty else int(checked_rows.iloc[0]['id'])
            st.session_state['detail_order_id'] = new_id
            if 'orders_editor' in st.session_state:
                del st.session_state['orders_editor']
            st.rerun()
        elif len(checked_rows) == 1:
            new_id = int(checked_rows.iloc[0]['id'])
            if new_id != st.session_state.get('detail_order_id'):
                st.session_state['detail_order_id'] = new_id
        else:
            st.session_state['detail_order_id'] = None

        checked = checked_rows
        if not checked.empty:
            selected_id = int(checked.iloc[0]['id'])
            vhsys_label = checked.iloc[0]['Pedido']
            st.divider()
            st.subheader(f"Itens do Pedido {vhsys_label}")
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    items = [dict(r) for r in read_supplier_order_items(cursor, selected_id)]
                conn.close()
                if items:
                    df_items = pd.DataFrame(items)

                    _item_qty   = pd.to_numeric(df_items['quantity'],   errors='coerce')
                    _item_price = pd.to_numeric(df_items['price_unit'], errors='coerce')
                    _item_dt    = pd.to_datetime(df_items['created_at'], errors='coerce')

                    # dif_icms por unidade
                    _item_factor = _item_dt.ge(pd.Timestamp('2025-06-15')).map({True: 0.85 * 0.06, False: 0.06})
                    df_items['dif_icms'] = (_item_price * _item_factor).where(_item_price.notna(), other=None)

                    # frete + imposto por unidade
                    _ord_vf = pd.to_numeric(checked.iloc[0].get('Valor Faturado (R$)'), errors='coerce')
                    _ord_iv = pd.to_numeric(checked.iloc[0].get('Valor Produtos (R$)'), errors='coerce')
                    if pd.notna(_ord_vf) and pd.notna(_ord_iv) and _ord_iv != 0:
                        _ratio = (_ord_vf - _ord_iv) / _ord_iv
                        df_items['frete_imposto'] = (_item_price * _ratio).where(_item_price.notna(), other=None)
                    else:
                        df_items['frete_imposto'] = None

                    # preço real por unidade
                    _fi  = pd.to_numeric(df_items['frete_imposto'], errors='coerce').fillna(0)
                    _icms = pd.to_numeric(df_items['dif_icms'],     errors='coerce').fillna(0)
                    df_items['preco_real'] = (_item_price + _fi + _icms).where(_item_price.notna(), other=None)

                    _fmt = "R$ %.2f"
                    df_renamed = df_items.rename(columns={
                        'external_product_name': 'Produto Plataforma',
                        'external_category':     'Categoria',
                        'quantity':              'Qtd',
                        'price_unit':            'Preço Unit.',
                        'dif_icms':              'Dif. ICMS (R$)',
                        'frete_imposto':         'Frete + Imposto',
                        'preco_real':            'Preço Real',
                    }).drop(columns=['id', 'order_id', 'local_product_id', 'local_product_desc',
                                     'external_product_id', 'created_at', 'mapeado'], errors='ignore')

                    _cols = [c for c in [
                        'Produto Plataforma', 'Categoria', 'Qtd',
                        'Preço Unit.', 'Frete + Imposto', 'Dif. ICMS (R$)', 'Preço Real',
                    ] if c in df_renamed.columns]

                    st.dataframe(
                        df_renamed[_cols],
                        column_config={
                            'Qtd':            st.column_config.NumberColumn("Qtd",            format="%.3f"),
                            'Preço Unit.':    st.column_config.NumberColumn("Preço Unit.",    format=_fmt),
                            'Frete + Imposto':st.column_config.NumberColumn("Frete + Imposto",format=_fmt),
                            'Dif. ICMS (R$)': st.column_config.NumberColumn("Dif. ICMS (R$)",format=_fmt),
                            'Preço Real':     st.column_config.NumberColumn("Preço Real",     format=_fmt),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Pedido sem itens.")
            except Exception as e:
                st.error(f"Erro ao carregar itens: {e}")


# ── TAB 4: Preço Médio ───────────────────────────────────────────────────────
with tab_avg:
    st.subheader("Preço Médio por Caixa")
    st.caption(
        "Considera apenas pedidos com nota de produtos **e** nota de serviço preenchidas. "
        "O preço real por unidade = Preço Unit. × (1 + percentual frete + fator ICMS)."
    )

    from datetime import date, timedelta
    col_d1, col_d2, col_calc = st.columns([2, 2, 1])
    with col_d1:
        start_dt = st.date_input("De", value=date.today() - timedelta(days=90), key="avg_start")
    with col_d2:
        end_dt = st.date_input("Até", value=date.today(), key="avg_end")
    with col_calc:
        st.write("")
        calcular = st.button("Calcular", type="primary", use_container_width=True)

    if calcular:
        if start_dt > end_dt:
            st.warning("A data inicial deve ser anterior à data final.")
        else:
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    rows = [dict(r) for r in read_items_for_price_avg(cursor, start_dt, end_dt)]
                conn.close()
            except Exception as e:
                st.error(f"Erro ao carregar dados: {e}")
                rows = []

            if not rows:
                st.info("Nenhum item encontrado no período com notas preenchidas.")
            else:
                df_avg = pd.DataFrame(rows)

                _qty   = pd.to_numeric(df_avg['quantity'],          errors='coerce')
                _price = pd.to_numeric(df_avg['price_unit'],        errors='coerce')
                _oiv   = pd.to_numeric(df_avg['order_items_value'], errors='coerce')
                _vf    = pd.to_numeric(df_avg['valor_faturado'],    errors='coerce')
                _dt    = pd.to_datetime(df_avg['created_at'],       errors='coerce')

                _factor = _dt.ge(pd.Timestamp('2025-06-15')).map({True: 0.85 * 0.06, False: 0.06})
                _ratio  = ((_vf - _oiv) / _oiv).where(_oiv != 0, other=0)

                df_avg['_qty_n']          = _qty
                df_avg['preco_real_unit'] = _price * (1 + _ratio + _factor)
                df_avg['valor_real_item'] = _qty * df_avg['preco_real_unit']
                df_avg['valor_unit_item'] = _qty * _price

                result = df_avg.groupby('product_desc').agg(
                    Categoria          =('external_category', 'first'),
                    qtd_total          =('_qty_n',            'sum'),
                    soma_valor_unit    =('valor_unit_item',   'sum'),
                    soma_valor_real    =('valor_real_item',   'sum'),
                ).reset_index()

                result['Preço Unit. Médio'] = result['soma_valor_unit'] / result['qtd_total']
                result['Preço Real Médio']  = result['soma_valor_real'] / result['qtd_total']
                result['Dif. por Caixa']    = result['Preço Real Médio'] - result['Preço Unit. Médio']

                result = result.rename(columns={
                    'product_desc': 'Produto',
                    'qtd_total':    'Qtd Total',
                }).drop(columns=['soma_valor_unit', 'soma_valor_real'])

                result = result.sort_values('Produto')

                _fmt = "R$ %.2f"
                st.dataframe(
                    result[['Produto', 'Categoria', 'Qtd Total',
                             'Preço Unit. Médio', 'Dif. por Caixa', 'Preço Real Médio']],
                    column_config={
                        'Qtd Total':        st.column_config.NumberColumn("Qtd Total",        format="%.0f"),
                        'Preço Unit. Médio':st.column_config.NumberColumn("Preço Unit. Médio",format=_fmt),
                        'Dif. por Caixa':   st.column_config.NumberColumn("Dif. por Caixa",   format=_fmt),
                        'Preço Real Médio': st.column_config.NumberColumn("Preço Real Médio", format=_fmt),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

                st.divider()
                st.subheader("Médias por Categoria")

                cat_totals = result.groupby('Categoria').apply(
                    lambda g: pd.Series({
                        'Qtd Total':         g['Qtd Total'].sum(),
                        'Preço Unit. Médio': (g['Preço Unit. Médio'] * g['Qtd Total']).sum() / g['Qtd Total'].sum(),
                        'Preço Real Médio':  (g['Preço Real Médio']  * g['Qtd Total']).sum() / g['Qtd Total'].sum(),
                    })
                ).reset_index()
                cat_totals['Dif. por Caixa'] = cat_totals['Preço Real Médio'] - cat_totals['Preço Unit. Médio']

                st.dataframe(
                    cat_totals[['Categoria', 'Qtd Total', 'Preço Unit. Médio', 'Dif. por Caixa', 'Preço Real Médio']],
                    column_config={
                        'Qtd Total':         st.column_config.NumberColumn("Qtd Total",         format="%.0f"),
                        'Preço Unit. Médio': st.column_config.NumberColumn("Preço Unit. Médio", format=_fmt),
                        'Dif. por Caixa':    st.column_config.NumberColumn("Dif. por Caixa",    format=_fmt),
                        'Preço Real Médio':  st.column_config.NumberColumn("Preço Real Médio",  format=_fmt),
                    },
                    use_container_width=True,
                    hide_index=True,
                )


# ── TAB 5: Análise de Itens ──────────────────────────────────────────────────
with tab_freq:
    st.subheader("Itens mais comuns nos pedidos")
    st.caption("Frequência e quantidade média de cada produto com base nos pedidos importados.")

    from datetime import date, timedelta
    col_a1, col_a2, col_a3 = st.columns([2, 2, 1])
    with col_a1:
        freq_start = st.date_input("De", value=date.today() - timedelta(days=180), key="freq_start")
    with col_a2:
        freq_end = st.date_input("Até", value=date.today(), key="freq_end")
    with col_a3:
        st.write("")
        freq_calcular = st.button("Calcular", type="primary", use_container_width=True, key="freq_btn")

    if freq_calcular:
        if freq_start > freq_end:
            st.warning("A data inicial deve ser anterior à data final.")
        else:
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    rows = [dict(r) for r in read_item_frequency(cursor, freq_start, freq_end)]
                conn.close()
            except Exception as e:
                st.error(f"Erro ao carregar dados: {e}")
                rows = []

            if not rows:
                st.info("Nenhum item encontrado no período.")
            else:
                df_freq = pd.DataFrame(rows)
                df_freq['num_pedidos'] = pd.to_numeric(df_freq['num_pedidos'], errors='coerce')
                df_freq['qty_total']   = pd.to_numeric(df_freq['qty_total'],   errors='coerce')
                df_freq['qty_media']   = pd.to_numeric(df_freq['qty_media'],   errors='coerce')

                total_pedidos = df_freq['num_pedidos'].max()
                df_freq['% pedidos'] = (df_freq['num_pedidos'] / total_pedidos * 100).round(1)

                df_freq = df_freq.rename(columns={
                    'product_desc':      'Produto',
                    'external_category': 'Categoria',
                    'num_pedidos':       'Nº Pedidos',
                    'qty_total':         'Qtd Total',
                    'qty_media':         'Qtd Média/Pedido',
                })

                st.session_state['freq_df']            = df_freq
                st.session_state['freq_total_pedidos'] = int(total_pedidos)

    if 'freq_df' in st.session_state:
        df_freq = st.session_state['freq_df']
        total_pedidos = st.session_state['freq_total_pedidos']

        c1, c2 = st.columns(2)
        with c1:
            cats = ['Todas'] + sorted(df_freq['Categoria'].dropna().unique().tolist())
            cat_filter = st.selectbox("Categoria", cats, key="freq_cat")
        with c2:
            busca_prod = st.text_input("Buscar produto", key="freq_busca")

        df_show = df_freq.copy()
        if cat_filter != 'Todas':
            df_show = df_show[df_show['Categoria'] == cat_filter]
        if busca_prod.strip():
            df_show = df_show[df_show['Produto'].str.contains(busca_prod.strip(), case=False, na=False)]

        st.dataframe(
            df_show[['Produto', 'Categoria', 'Nº Pedidos', '% pedidos', 'Qtd Total', 'Qtd Média/Pedido']],
            column_config={
                'Nº Pedidos':       st.column_config.NumberColumn("Nº Pedidos",       format="%d"),
                '% pedidos':        st.column_config.NumberColumn("% dos pedidos",    format="%.1f%%"),
                'Qtd Total':        st.column_config.NumberColumn("Qtd Total",        format="%.0f"),
                'Qtd Média/Pedido': st.column_config.NumberColumn("Qtd Média/Pedido", format="%.2f"),
            },
            use_container_width=True,
            hide_index=True,
        )

        st.caption(f"Baseado em {total_pedidos} pedido(s) com itens no período.")
