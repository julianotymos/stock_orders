from typing import List


def read_products_config(cursor) -> List[dict]:
    """
    Retorna todos os produtos com status, contagem de caixas e último movimento.
    last_movement via subquery correlacionada para evitar fan-out com o histórico.
    """
    query = """
        SELECT
            p.id,
            p.description                                                           AS product_desc,
            p.product_type,
            p.status                                                                AS status_id,
            COUNT(DISTINCT fp.id)                                                   AS total_positions,
            COUNT(DISTINCT CASE WHEN sf.status_code = 'OPEN'   THEN fp.id END)     AS open_qty,
            COUNT(DISTINCT CASE WHEN sf.status_code = 'CLOSED' THEN fp.id END)     AS closed_qty,
            (SELECT MAX(fph.change_date)
             FROM FREEZER_POSITION_HISTORY fph
             WHERE fph.product = p.id)                                              AS last_movement,
            CASE WHEN pe.product_id IS NOT NULL THEN TRUE ELSE FALSE END            AS excluir_calculos
        FROM PRODUCT p
        LEFT JOIN FREEZER_POSITION  fp  ON fp.product   = p.id
        LEFT JOIN STATUS            sf  ON sf.id        = fp.status
        LEFT JOIN PRODUCT_EXCLUDE   pe  ON pe.product_id = p.id
        GROUP BY p.id, p.description, p.product_type, p.status, pe.product_id
        ORDER BY p.description
    """
    cursor.execute(query)
    return cursor.fetchall()
