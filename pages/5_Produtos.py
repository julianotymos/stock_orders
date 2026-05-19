import streamlit as st
import pandas as pd

from db_config import get_db_connection
from functions_modules.read_products_config import read_products_config
from functions_modules.update_product_active import update_product_status
from functions_modules.update_product_exclude import set_product_exclude
from functions_modules.create_product import create_product

STATUS_ATIVO   = 1
STATUS_INATIVO = 2

PRODUCT_TYPES = ["Açaí", "Sorvete", "Sorbet", "Vazio", "Balde", "Outro"]

st.set_page_config(page_title="Produtos", page_icon="🧊", layout="wide")
st.title("🧊 Gestão de Produtos")

tab_lista, tab_cadastro = st.tabs(["Lista de Produtos", "Cadastrar Produto"])


@st.cache_data(ttl=60)
def load_products() -> list:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            return [dict(r) for r in read_products_config(cursor)]
    finally:
        conn.close()


# ── TAB CADASTRO ─────────────────────────────────────────────────────────────
with tab_cadastro:
    st.subheader("Novo produto")
    with st.form("form_cadastro"):
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            product_name = st.text_input("Nome curto (product_name)", placeholder="Ex: acai-morango")
        with col_n2:
            description = st.text_input("Descrição (description)", placeholder="Ex: Açaí Morango 6kg")
        col_tipo, col_size, col_sort = st.columns(3)
        with col_tipo:
            tipo = st.selectbox("Tipo", PRODUCT_TYPES)
        with col_size:
            tamanho = st.text_input("Tamanho (product_size)", placeholder="Ex: 6kg, 3L...")
        with col_sort:
            sort_order = st.number_input("Ordem de exibição (sort_order)", min_value=0, value=0, step=1)
        excluir = st.checkbox(
            "Excluir de cálculos (Vazio / Balde)",
            help="Produto ficará ativo para uso nas posições, mas ignorado em consumo e sugestão de pedido."
        )
        submitted = st.form_submit_button("Cadastrar", type="primary")

    if submitted:
        if not product_name.strip():
            st.warning("Informe o nome curto do produto (product_name).")
        elif not description.strip():
            st.warning("Informe a descrição do produto.")
        else:
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    new_id = create_product(
                        cursor,
                        product_name=product_name,
                        description=description,
                        product_type=tipo,
                        product_size=tamanho or None,
                        sort_order=sort_order if sort_order > 0 else None,
                    )
                    if excluir:
                        from functions_modules.update_product_exclude import set_product_exclude
                        set_product_exclude(cursor, new_id, True, reason="Cadastrado como placeholder")
                    conn.commit()
                conn.close()
                st.success(f"Produto **{description}** cadastrado com ID #{new_id}.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")


# ── TAB LISTA ─────────────────────────────────────────────────────────────────
with tab_lista:
    st.caption(
        "Gerencie o status dos produtos e defina quais ficam fora dos cálculos de consumo e pedido. "
        "Produtos como 'Vazio' e 'Balde' podem permanecer ativos para uso nas posições, "
        "mas marcados como 'Excluir de cálculos' para não aparecerem em sugestões de pedido."
    )

    try:
        products = load_products()

        if not products:
            st.warning("Nenhum produto encontrado.")
            st.stop()

        df = pd.DataFrame(products)
        df['ativo']            = df['status_id'] == STATUS_ATIVO
        df['excluir_calculos'] = df['excluir_calculos'].astype(bool)

        total     = len(df)
        ativos    = int(df['ativo'].sum())
        inativos  = total - ativos
        excluidos = int(df['excluir_calculos'].sum())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total de produtos", total)
        m2.metric("Ativos",   ativos)
        m3.metric("Inativos", inativos)
        m4.metric("Fora dos calculos", excluidos,
                  help="Produtos como Vazio e Balde: ativos para uso mas ignorados em consumo/pedido")

        st.divider()

        col_busca, col_filtro, col_refresh = st.columns([3, 1, 1])
        with col_busca:
            busca = st.text_input("Buscar produto", placeholder="Digite parte do nome...")
        with col_filtro:
            filtro = st.selectbox("Exibir", ["Todos", "Apenas ativos", "Apenas inativos", "Excluidos de calculos"])
        with col_refresh:
            st.write("")
            if st.button("Atualizar", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        df_show = df.copy()
        if busca:
            df_show = df_show[df_show['product_desc'].str.contains(busca, case=False, na=False)]
        if filtro == "Apenas ativos":
            df_show = df_show[df_show['ativo'] == True]
        elif filtro == "Apenas inativos":
            df_show = df_show[df_show['ativo'] == False]
        elif filtro == "Excluidos de calculos":
            df_show = df_show[df_show['excluir_calculos'] == True]

        st.subheader(f"Produtos ({len(df_show)} exibidos)")

        edited = st.data_editor(
            df_show,
            key="produtos_editor",
            column_config={
                'id':              None,
                'status_id':       None,
                'product_desc':    st.column_config.TextColumn("Produto", disabled=True, width="large"),
                'product_type':    st.column_config.TextColumn("Tipo", disabled=True),
                'ativo':           st.column_config.CheckboxColumn(
                                       "Ativo",
                                       help="Status 1=ativo, 2=inativo. Desmarque para inativar."
                                   ),
                'excluir_calculos': st.column_config.CheckboxColumn(
                                       "Excluir de calculos",
                                       help=(
                                           "Marque para produtos como Vazio e Balde: "
                                           "continuam ativos para uso nas posicoes, "
                                           "mas sao ignorados em consumo e sugestoes de pedido."
                                       )
                                   ),
                'total_positions': st.column_config.NumberColumn("Posicoes", disabled=True),
                'open_qty':        st.column_config.NumberColumn(
                                       "Caixas abertas", disabled=True,
                                       help="Caixas abertas (em consumo) neste produto"
                                   ),
                'closed_qty':      st.column_config.NumberColumn(
                                       "Caixas fechadas", disabled=True,
                                       help="Caixas fechadas (nao abertas ainda) neste produto"
                                   ),
                'last_movement':   st.column_config.DatetimeColumn(
                                       "Ultima troca", disabled=True,
                                       format="DD/MM/YYYY HH:mm"
                                   ),
            },
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        if st.button("Salvar alteracoes", type="primary"):
            original_ativo    = df_show.set_index('id')['ativo']
            original_excluido = df_show.set_index('id')['excluir_calculos']
            novo_ativo        = edited.set_index('id')['ativo']
            novo_excluido     = edited.set_index('id')['excluir_calculos']

            status_alterados  = novo_ativo[novo_ativo != original_ativo].reset_index()
            excluir_alterados = novo_excluido[novo_excluido != original_excluido].reset_index()

            if status_alterados.empty and excluir_alterados.empty:
                st.info("Nenhuma alteracao detectada.")
            else:
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        for _, row in status_alterados.iterrows():
                            novo_status = STATUS_ATIVO if row['ativo'] else STATUS_INATIVO
                            update_product_status(cursor, int(row['id']), novo_status)

                        for _, row in excluir_alterados.iterrows():
                            set_product_exclude(
                                cursor,
                                int(row['id']),
                                bool(row['excluir_calculos']),
                                reason="Produto placeholder (Vazio/Balde) — excluido de calculos"
                            )
                        conn.commit()
                    conn.close()
                    st.cache_data.clear()

                    partes = []
                    if not status_alterados.empty:
                        a = int(status_alterados['ativo'].sum())
                        i = len(status_alterados) - a
                        if a: partes.append(f"{a} ativado(s)")
                        if i: partes.append(f"{i} desativado(s)")
                    if not excluir_alterados.empty:
                        e = int(excluir_alterados['excluir_calculos'].sum())
                        r = len(excluir_alterados) - e
                        if e: partes.append(f"{e} excluido(s) de calculos")
                        if r: partes.append(f"{r} incluido(s) de volta nos calculos")

                    st.success(f"Salvo: {', '.join(partes)}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

        with st.expander("O que significa cada coluna?"):
            st.markdown("""
            | Coluna | Significado |
            |--------|-------------|
            | **Ativo** | Status 1=ativo, 2=inativo. Produto inativo nao aparece na lista de selecao de posicoes |
            | **Excluir de calculos** | Produto fica ativo para uso nas posicoes, mas e ignorado no consumo e sugestao de pedido |
            | **Caixas abertas** | Posicoes onde a caixa fisica esta aberta (em consumo) |
            | **Caixas fechadas** | Posicoes onde a caixa fisica esta fechada (nao aberta ainda) |

            **Uso tipico de "Excluir de calculos":**
            - **Vazio** — marca posicao disponivel. Nao e produto real, nao deve ser contado como consumo
            - **Balde** — posicao de acesso ruim, permanece com balde e nao sera reposta
            """)

    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
