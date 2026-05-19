import os
import streamlit as st

# Inject Streamlit Cloud secrets as env vars so os.getenv() works in all modules
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

from db_config import get_db_connection

st.set_page_config(
    page_title="The Best Stock — Pedidos",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📦 The Best Stock — Sistema de Pedidos")
st.markdown("Sistema de análise de consumo e geração automática de pedidos de reposição para freezers.")
st.divider()

col1, col2 = st.columns(2)
with col1:
    st.info("**📊 Estoque**\nVisualiza estoque atual por produto e freezer, com gráfico de consumo histórico.")
    st.info("**🛒 Gerar Pedido**\nAnalisa consumo, compara com estoque mínimo e cria pedidos de reposição.")
with col2:
    st.info("**📋 Pedidos**\nAcompanha pedidos gerados e permite atualizar o status de cada um.")
    st.info("**⚙️ Configurações**\nDefine estoque mínimo e alvo de reposição por produto.")

st.divider()

# Verifica conexão e existência das tabelas novas
st.subheader("Status do sistema")
try:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1")
    conn.close()
    st.success("Banco de dados conectado.")
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# Verifica tabelas novas e cria se não existirem
try:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS STOCK_MINIMUM (
                ID          SERIAL PRIMARY KEY,
                PRODUCT     INT  NOT NULL REFERENCES PRODUCT(ID),
                MIN_QTY     INT  NOT NULL DEFAULT 0,
                TARGET_QTY  INT  NOT NULL DEFAULT 0,
                PERIOD_DAYS INT  NOT NULL DEFAULT 30,
                UPDATED_AT  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_stock_minimum_product UNIQUE (PRODUCT)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PURCHASE_ORDER (
                ID          SERIAL PRIMARY KEY,
                ORDER_DATE  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                STATUS      VARCHAR(20) NOT NULL DEFAULT 'RASCUNHO',
                PERIOD_DAYS INT,
                NOTES       TEXT,
                CREATED_BY  VARCHAR(100)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PURCHASE_ORDER_ITEM (
                ID                    SERIAL PRIMARY KEY,
                ORDER_ID              INT           NOT NULL REFERENCES PURCHASE_ORDER(ID) ON DELETE CASCADE,
                PRODUCT               INT           NOT NULL REFERENCES PRODUCT(ID),
                CURRENT_STOCK         INT,
                MIN_QTY               INT,
                TARGET_QTY            INT,
                AVG_DAILY_CONSUMPTION NUMERIC(10,4),
                SUGGESTED_QTY         INT,
                CONFIRMED_QTY         INT,
                SUPPLIER_AVAILABLE    BOOLEAN,
                SUPPLIER_PRICE        NUMERIC(10,2),
                NOTES                 TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PRODUCT_EXCLUDE (
                PRODUCT_ID INT  NOT NULL REFERENCES PRODUCT(ID) ON DELETE CASCADE,
                REASON     TEXT,
                CONSTRAINT pk_product_exclude PRIMARY KEY (PRODUCT_ID)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PRODUCT_MAPPING (
                external_product_id  INT          NOT NULL,
                external_name        VARCHAR(200) NOT NULL,
                local_product_id     INT          REFERENCES PRODUCT(ID),
                updated_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT pk_product_mapping PRIMARY KEY (external_product_id)
            )
        """)
        cursor.execute("""
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
        cursor.execute("""
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
        conn.commit()
    conn.close()
    st.success("Tabelas verificadas.")
except Exception as e:
    st.warning(f"Atenção ao verificar tabelas: {e}\nExecute manualmente o arquivo sql/create_tables.sql no Supabase.")
