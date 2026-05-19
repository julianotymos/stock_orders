from typing import List, Optional


def read_product_mapping(cursor) -> List[dict]:
    """Retorna todos os mapeamentos externos → locais, com nome do produto local."""
    cursor.execute("""
        SELECT
            pm.external_product_id,
            pm.external_name,
            pm.local_product_id,
            p.description AS local_product_desc
        FROM PRODUCT_MAPPING pm
        LEFT JOIN PRODUCT p ON p.id = pm.local_product_id
        ORDER BY pm.external_name
    """)
    return cursor.fetchall()


def upsert_product_mapping(cursor, external_product_id: int, external_name: str,
                           local_product_id: Optional[int]) -> None:
    """Insere ou atualiza o mapeamento de um produto externo para um produto local."""
    cursor.execute("""
        INSERT INTO PRODUCT_MAPPING (external_product_id, external_name, local_product_id)
        VALUES (%(ext_id)s, %(ext_name)s, %(local_id)s)
        ON CONFLICT (external_product_id)
        DO UPDATE SET
            external_name    = EXCLUDED.external_name,
            local_product_id = EXCLUDED.local_product_id,
            updated_at       = CURRENT_TIMESTAMP
    """, {
        'ext_id':   external_product_id,
        'ext_name': external_name,
        'local_id': local_product_id,
    })


def sync_mapping_to_order_items(cursor) -> int:
    """
    Propaga os mapeamentos já confirmados para SUPPLIER_ORDER_ITEM.
    Atualiza local_product_id nos itens que ainda estão NULL.
    Retorna número de linhas atualizadas.
    """
    cursor.execute("""
        UPDATE SUPPLIER_ORDER_ITEM soi
        SET local_product_id = pm.local_product_id
        FROM PRODUCT_MAPPING pm
        WHERE soi.external_product_id = pm.external_product_id
          AND pm.local_product_id IS NOT NULL
          AND soi.local_product_id IS NULL
    """)
    return cursor.rowcount


def read_local_products(cursor) -> List[dict]:
    """Lista produtos locais (ativos e inativos) para exibir no selectbox de normalização."""
    cursor.execute("""
        SELECT id, description, status
        FROM PRODUCT
        ORDER BY status, description
    """)
    return cursor.fetchall()
