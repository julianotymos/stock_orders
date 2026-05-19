from typing import List


def calculate_order_suggestions(cursor, days: int = 30, include_no_position: bool = False) -> List[dict]:
    """
    Calcula sugestão de pedido por produto combinando:
    - Média de consumo diário (últimos N dias, via FREEZER_POSITION_HISTORY)
    - Estoque mínimo configurado em STOCK_MINIMUM

    Regra de negócio:
      - Caixas FECHADAS = estoque disponível para pedido (ainda não abertas)
      - Caixas ABERTAS  = em consumo na loja, não contam como estoque
      - Pede quando closed_qty <= min_qty  OU  closed_qty < consumo projetado no período
    """
    query = """
        WITH consumption AS (
            SELECT
                fph.product,
                COUNT(*)                                    AS total_consumed,
                ROUND(COUNT(*)::numeric / %(days)s, 4)     AS avg_daily
            FROM FREEZER_POSITION_HISTORY fph
            WHERE fph.change_date >= CURRENT_TIMESTAMP - (%(days)s * INTERVAL '1 day')
              AND fph.product NOT IN (SELECT product_id FROM PRODUCT_EXCLUDE)
            GROUP BY fph.product
        ),
        current_stock AS (
            SELECT
                fp.product,
                COUNT(*)                                                    AS total_positions,
                SUM(CASE WHEN s.status_code = 'OPEN'   THEN 1 ELSE 0 END)  AS open_qty,
                SUM(CASE WHEN s.status_code = 'CLOSED' THEN 1 ELSE 0 END)  AS closed_qty
            FROM FREEZER_POSITION fp
            INNER JOIN STATUS s ON s.id = fp.status
            GROUP BY fp.product
        ),
        min_cfg AS (
            SELECT product, min_qty, target_qty
            FROM STOCK_MINIMUM
        ),
        platform_avg AS (
            SELECT
                pm.local_product_id,
                ROUND(
                    SUM(soi.quantity) / NULLIF(COUNT(DISTINCT soi.order_id), 0)::numeric,
                    2
                ) AS avg_qty_platform
            FROM SUPPLIER_ORDER_ITEM soi
            JOIN PRODUCT_MAPPING pm ON pm.external_product_id = soi.external_product_id
            WHERE soi.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
            GROUP BY pm.local_product_id
        )
        SELECT
            p.id,
            COALESCE(pm.external_name, p.description)               AS product_desc,
            p.description                                            AS local_desc,
            p.product_type,
            COALESCE(cs.total_positions, 0)                         AS total_positions,
            COALESCE(cs.open_qty,        0)                         AS open_qty,
            COALESCE(cs.closed_qty,      0)                         AS closed_qty,
            COALESCE(mc.min_qty,         0)                         AS min_qty,
            COALESCE(mc.target_qty,      0)                         AS target_qty,
            COALESCE(c.total_consumed,   0)                         AS total_consumed,
            COALESCE(c.avg_daily,        0)                         AS avg_daily_consumption,
            COALESCE(pa.avg_qty_platform, 0)                        AS avg_platform_30d,
            CASE
                WHEN COALESCE(cs.closed_qty, 0) <= COALESCE(mc.min_qty, 0)
                  OR COALESCE(cs.closed_qty, 0) < CEIL(COALESCE(c.avg_daily, 0) * %(days)s)
                THEN GREATEST(
                    COALESCE(mc.target_qty, 0) - COALESCE(cs.closed_qty, 0),
                    CEIL(COALESCE(c.avg_daily, 0) * %(days)s)::INT - COALESCE(cs.closed_qty, 0),
                    0
                )
                ELSE 0
            END                                                      AS suggested_qty
        FROM PRODUCT p
        LEFT  JOIN current_stock cs ON cs.product = p.id
        LEFT  JOIN consumption   c  ON c.product  = p.id
        LEFT  JOIN min_cfg       mc ON mc.product  = p.id
        LEFT  JOIN PRODUCT_MAPPING pm ON pm.local_product_id = p.id
        LEFT  JOIN platform_avg  pa ON pa.local_product_id  = p.id
        WHERE (cs.total_positions > 0 OR %(include_no_position)s)
          AND p.status = 1
          AND p.id NOT IN (SELECT product_id FROM PRODUCT_EXCLUDE)
        ORDER BY suggested_qty DESC, p.description
    """
    cursor.execute(query, {'days': days, 'include_no_position': include_no_position})
    return cursor.fetchall()
