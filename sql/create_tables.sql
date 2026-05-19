-- Configuração de estoque mínimo e alvo por produto
CREATE TABLE IF NOT EXISTS STOCK_MINIMUM (
    ID          SERIAL PRIMARY KEY,
    PRODUCT     INT  NOT NULL REFERENCES PRODUCT(ID),
    MIN_QTY     INT  NOT NULL DEFAULT 0,
    TARGET_QTY  INT  NOT NULL DEFAULT 0,
    PERIOD_DAYS INT  NOT NULL DEFAULT 30,
    UPDATED_AT  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stock_minimum_product UNIQUE (PRODUCT)
);

-- Cabeçalho do pedido de compra
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER (
    ID          SERIAL PRIMARY KEY,
    ORDER_DATE  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    STATUS      VARCHAR(20)  NOT NULL DEFAULT 'RASCUNHO',  -- RASCUNHO | CONFIRMADO | ENVIADO | RECEBIDO
    PERIOD_DAYS INT,
    NOTES       TEXT,
    CREATED_BY  VARCHAR(100)
);

-- Itens do pedido de compra
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
);

-- Produtos excluídos de cálculos de consumo e sugestão de pedido
-- (ex: "Vazio" e "Balde" — usados para marcar posições, não são produtos reais)
CREATE TABLE IF NOT EXISTS PRODUCT_EXCLUDE (
    PRODUCT_ID  INT  NOT NULL REFERENCES PRODUCT(ID) ON DELETE CASCADE,
    REASON      TEXT,
    CONSTRAINT pk_product_exclude PRIMARY KEY (PRODUCT_ID)
);

-- Mapeamento de produtos externos (plataforma) para produtos locais
CREATE TABLE IF NOT EXISTS PRODUCT_MAPPING (
    external_product_id  INT          NOT NULL,
    external_name        VARCHAR(200) NOT NULL,
    local_product_id     INT          REFERENCES PRODUCT(ID),
    updated_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_product_mapping PRIMARY KEY (external_product_id)
);

-- Pedidos importados da plataforma The Best (amatech)
CREATE TABLE IF NOT EXISTS SUPPLIER_ORDER (
    id                  SERIAL PRIMARY KEY,
    platform_order_id   INT          NOT NULL,
    store_id            INT,
    platform_status     INT,
    total               NUMERIC(12,2),
    franchise_tax       NUMERIC(12,2),
    loaded_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_supplier_order_platform UNIQUE (platform_order_id)
);

-- Itens dos pedidos da plataforma
CREATE TABLE IF NOT EXISTS SUPPLIER_ORDER_ITEM (
    id                   SERIAL PRIMARY KEY,
    order_id             INT          NOT NULL REFERENCES SUPPLIER_ORDER(ID) ON DELETE CASCADE,
    platform_item_id     INT,
    external_product_id  INT,
    external_product_name VARCHAR(200),
    external_category    VARCHAR(100),
    quantity             NUMERIC(10,3),
    price_unit           NUMERIC(10,2),
    local_product_id     INT          REFERENCES PRODUCT(ID),
    created_at           TIMESTAMP
);

-- Índices úteis
CREATE INDEX IF NOT EXISTS idx_poi_order_id  ON PURCHASE_ORDER_ITEM (ORDER_ID);
CREATE INDEX IF NOT EXISTS idx_poi_product    ON PURCHASE_ORDER_ITEM (PRODUCT);
CREATE INDEX IF NOT EXISTS idx_po_status      ON PURCHASE_ORDER (STATUS);
CREATE INDEX IF NOT EXISTS idx_po_order_date  ON PURCHASE_ORDER (ORDER_DATE);
CREATE INDEX IF NOT EXISTS idx_soi_order_id   ON SUPPLIER_ORDER_ITEM (order_id);
CREATE INDEX IF NOT EXISTS idx_soi_ext_pid    ON SUPPLIER_ORDER_ITEM (external_product_id);
CREATE INDEX IF NOT EXISTS idx_so_loaded_at   ON SUPPLIER_ORDER (loaded_at);
