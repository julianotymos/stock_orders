from typing import List


def read_stock_minimum(cursor) -> List[dict]:
    """Lê configuração de estoque mínimo para todos os produtos que existem em freezers."""
    query = """
        SELECT
            p.id                             AS product_id,
            p.description                    AS product_desc,
            p.product_type,
            COALESCE(sm.min_qty,     0)      AS min_qty,
            COALESCE(sm.target_qty,  0)      AS target_qty,
            COALESCE(sm.period_days, 30)     AS period_days,
            sm.updated_at
        FROM PRODUCT p
        INNER JOIN (
            SELECT DISTINCT product FROM FREEZER_POSITION
        ) fp ON fp.product = p.id
        LEFT JOIN STOCK_MINIMUM sm ON sm.product = p.id
        ORDER BY p.description
    """
    cursor.execute(query)
    return cursor.fetchall()
