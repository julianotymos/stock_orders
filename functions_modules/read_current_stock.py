import psycopg2
from typing import List


def read_empty_positions_count(cursor) -> int:
    """Retorna posições com produto tipo 'Vazio' e status CLOSED (disponíveis para produto)."""
    cursor.execute("""
        SELECT COUNT(*) AS empty_positions
        FROM FREEZER_POSITION fp
        JOIN PRODUCT p ON p.id = fp.product
        JOIN STATUS  s ON s.id = fp.status
        WHERE p.product_type = 'Vazio'
          AND s.status_code = 'CLOSED'
    """)
    row = cursor.fetchone()
    return int(row['empty_positions']) if row else 0


def read_current_stock(cursor) -> List[dict]:
    query = """
        SELECT
            p.id,
            p.description                                               AS product_desc,
            p.product_type,
            f.id                                                        AS freezer_id,
            f.freezer_name,
            COUNT(*)                                                    AS total_positions,
            SUM(CASE WHEN s.status_code = 'OPEN'   THEN 1 ELSE 0 END) AS open_qty,
            SUM(CASE WHEN s.status_code = 'CLOSED' THEN 1 ELSE 0 END) AS closed_qty,
            MAX(fp.update_date)                                         AS last_update
        FROM FREEZER_POSITION fp
        INNER JOIN PRODUCT p ON p.id = fp.product
        INNER JOIN FREEZER f ON f.id = fp.freezer
        INNER JOIN STATUS  s ON s.id = fp.status
        WHERE p.id NOT IN (SELECT product_id FROM PRODUCT_EXCLUDE)
        GROUP BY p.id, p.description, p.product_type, f.id, f.freezer_name
        ORDER BY p.description, f.freezer_name
    """
    cursor.execute(query)
    return cursor.fetchall()
