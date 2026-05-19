from typing import List, Optional


def read_orders(cursor, status: Optional[str] = None) -> List[dict]:
    where = "WHERE 1=1"
    params: dict = {}
    if status:
        where += " AND po.status = %(status)s"
        params['status'] = status

    query = f"""
        SELECT
            po.id,
            po.order_date,
            po.status,
            po.period_days,
            po.notes,
            po.created_by,
            COUNT(poi.id)                AS total_items,
            COALESCE(SUM(poi.confirmed_qty), 0) AS total_qty
        FROM PURCHASE_ORDER po
        LEFT JOIN PURCHASE_ORDER_ITEM poi ON poi.order_id = po.id
        {where}
        GROUP BY po.id, po.order_date, po.status, po.period_days, po.notes, po.created_by
        ORDER BY po.order_date DESC
    """
    cursor.execute(query, params)
    return cursor.fetchall()


def read_order_items(cursor, order_id: int) -> List[dict]:
    query = """
        SELECT
            p.description            AS product_desc,
            p.product_type,
            poi.current_stock,
            poi.min_qty,
            poi.target_qty,
            poi.avg_daily_consumption,
            poi.suggested_qty,
            poi.confirmed_qty,
            poi.supplier_available,
            poi.supplier_price,
            poi.notes
        FROM PURCHASE_ORDER_ITEM poi
        INNER JOIN PRODUCT p ON p.id = poi.product
        WHERE poi.order_id = %(order_id)s
        ORDER BY poi.confirmed_qty DESC NULLS LAST, p.description
    """
    cursor.execute(query, {'order_id': order_id})
    return cursor.fetchall()


def update_order_status(cursor, order_id: int, new_status: str) -> int:
    query = """
        UPDATE PURCHASE_ORDER
        SET status = %(status)s
        WHERE id   = %(order_id)s
    """
    cursor.execute(query, {'status': new_status, 'order_id': order_id})
    return cursor.rowcount
