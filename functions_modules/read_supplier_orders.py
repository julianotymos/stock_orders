from typing import List


def read_supplier_orders(cursor) -> List[dict]:
    """Retorna cabeçalhos dos pedidos da plataforma salvos."""
    cursor.execute("""
        SELECT
            so.id,
            so.platform_order_id,
            so.vhsys,
            so.platform_status,
            so.total,
            so.product_invoice_value,
            so.product_invoice_doc,
            so.service_invoice_value,
            so.service_invoice_doc,
            so.loaded_at,
            MIN(soi.created_at)                             AS order_date,
            COUNT(soi.id)                                   AS total_items,
            SUM(soi.quantity)                               AS total_qty,
            ROUND(SUM(soi.quantity * soi.price_unit), 2)    AS items_value,
            SUM(CASE WHEN soi.local_product_id IS NULL
                          AND LOWER(soi.external_category) IN ('sorvetes', 'acai')
                     THEN 1 ELSE 0 END)                     AS unmapped_items
        FROM SUPPLIER_ORDER so
        LEFT JOIN SUPPLIER_ORDER_ITEM soi ON soi.order_id = so.id
        GROUP BY so.id, so.platform_order_id, so.vhsys, so.platform_status,
                 so.total, so.product_invoice_value, so.product_invoice_doc,
                 so.service_invoice_value, so.service_invoice_doc, so.loaded_at
        ORDER BY MIN(soi.created_at) DESC NULLS LAST, so.loaded_at DESC
    """)
    return cursor.fetchall()


def read_supplier_order_items(cursor, order_id: int) -> List[dict]:
    """Retorna itens de um pedido específico com nome do produto local se mapeado."""
    cursor.execute("""
        SELECT
            soi.id,
            soi.external_product_id,
            soi.external_product_name,
            soi.external_category,
            soi.quantity,
            soi.price_unit,
            soi.created_at,
            soi.local_product_id,
            p.description AS local_product_desc
        FROM SUPPLIER_ORDER_ITEM soi
        LEFT JOIN PRODUCT p ON p.id = soi.local_product_id
        WHERE soi.order_id = %(order_id)s
        ORDER BY soi.external_product_name
    """, {'order_id': order_id})
    return cursor.fetchall()


def read_item_frequency(cursor, start_date, end_date) -> List[dict]:
    """
    Retorna frequência e quantidade média dos produtos nos pedidos,
    filtrado pelo created_at do item entre start_date e end_date.
    """
    cursor.execute("""
        SELECT
            COALESCE(p.description, soi.external_product_name) AS product_desc,
            soi.external_category,
            COUNT(DISTINCT soi.order_id)                            AS num_pedidos,
            SUM(soi.quantity)                                       AS qty_total,
            ROUND(SUM(soi.quantity) / COUNT(DISTINCT soi.order_id)::numeric, 2) AS qty_media
        FROM SUPPLIER_ORDER_ITEM soi
        LEFT JOIN PRODUCT p ON p.id = soi.local_product_id
        WHERE soi.created_at::date BETWEEN %(start)s AND %(end)s
        GROUP BY COALESCE(p.description, soi.external_product_name), soi.external_category
        ORDER BY num_pedidos DESC, qty_total DESC
    """, {'start': start_date, 'end': end_date})
    return cursor.fetchall()


def read_items_for_price_avg(cursor, start_date, end_date) -> List[dict]:
    """
    Retorna itens de pedidos que possuem nota de produtos E nota de serviço,
    com os totais do pedido necessários para calcular frete e ICMS por unidade.
    Filtra pelo created_at do item entre start_date e end_date (inclusive).
    """
    cursor.execute("""
        WITH order_totals AS (
            SELECT order_id,
                   SUM(quantity * price_unit) AS items_value
            FROM SUPPLIER_ORDER_ITEM
            GROUP BY order_id
        )
        SELECT
            COALESCE(p.description, soi.external_product_name) AS product_desc,
            soi.external_category,
            soi.quantity,
            soi.price_unit,
            soi.created_at,
            ot.items_value                                              AS order_items_value,
            so.product_invoice_value + so.service_invoice_value        AS valor_faturado
        FROM SUPPLIER_ORDER_ITEM soi
        JOIN SUPPLIER_ORDER  so ON so.id = soi.order_id
        JOIN order_totals    ot ON ot.order_id = soi.order_id
        LEFT JOIN PRODUCT     p ON p.id = soi.local_product_id
        WHERE so.product_invoice_value IS NOT NULL
          AND so.service_invoice_value IS NOT NULL
          AND soi.created_at::date BETWEEN %(start)s AND %(end)s
        ORDER BY product_desc
    """, {'start': start_date, 'end': end_date})
    return cursor.fetchall()


def read_unmapped_products(cursor) -> List[dict]:
    """
    Retorna produtos de sorvetes/acai que aparecem em pedidos salvos
    mas ainda não têm mapeamento para produto local.
    Outras categorias não precisam de mapeamento.
    """
    cursor.execute("""
        SELECT DISTINCT
            soi.external_product_id,
            soi.external_product_name,
            soi.external_category
        FROM SUPPLIER_ORDER_ITEM soi
        LEFT JOIN PRODUCT_MAPPING pm ON pm.external_product_id = soi.external_product_id
        WHERE pm.local_product_id IS NULL
          AND LOWER(soi.external_category) IN ('sorvetes', 'acai')
        ORDER BY soi.external_product_name
    """)
    return cursor.fetchall()
