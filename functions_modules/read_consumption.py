from typing import List


def read_consumption_summary(cursor, days: int = 30) -> List[dict]:
    """
    Totais de consumo por produto nos últimos N dias.
    Cada registro no histórico = uma troca de produto = uma unidade consumida,
    independente do status (trocas ocorrem de OPEN -> novo produto diretamente).
    """
    query = """
        SELECT
            p.id,
            p.description                                   AS product_desc,
            p.product_type,
            COUNT(*)                                        AS total_consumed,
            ROUND(COUNT(*)::numeric / %(days)s, 4)         AS avg_daily_consumption
        FROM FREEZER_POSITION_HISTORY fph
        INNER JOIN PRODUCT p ON p.id = fph.product
        WHERE fph.change_date >= CURRENT_TIMESTAMP - (%(days)s * INTERVAL '1 day')
          AND p.id NOT IN (SELECT product_id FROM PRODUCT_EXCLUDE)
        GROUP BY p.id, p.description, p.product_type
        ORDER BY total_consumed DESC
    """
    cursor.execute(query, {'days': days})
    return cursor.fetchall()


def read_consumption_over_time(cursor, days: int = 30) -> List[dict]:
    """Consumo agrupado por semana e produto, para gráfico de linha."""
    query = """
        SELECT
            DATE_TRUNC('week', fph.change_date)::date AS week,
            p.description                              AS product_desc,
            p.product_type,
            COUNT(*)                                   AS consumed
        FROM FREEZER_POSITION_HISTORY fph
        INNER JOIN PRODUCT p ON p.id = fph.product
        WHERE fph.change_date >= CURRENT_TIMESTAMP - (%(days)s * INTERVAL '1 day')
          AND p.id NOT IN (SELECT product_id FROM PRODUCT_EXCLUDE)
        GROUP BY 1, 2, 3
        ORDER BY 1, 2
    """
    cursor.execute(query, {'days': days})
    return cursor.fetchall()
