from typing import List, Dict


def save_order(cursor, period_days: int, notes: str, created_by: str, items: List[Dict]) -> int:
    """
    Salva um pedido de compra com seus itens.
    Retorna o ID do pedido criado.
    """
    order_query = """
        INSERT INTO PURCHASE_ORDER (period_days, notes, created_by, status)
        VALUES (%(period_days)s, %(notes)s, %(created_by)s, 'RASCUNHO')
        RETURNING id
    """
    cursor.execute(order_query, {
        'period_days': period_days,
        'notes':       notes,
        'created_by':  created_by,
    })
    order_id = cursor.fetchone()['id']

    item_query = """
        INSERT INTO PURCHASE_ORDER_ITEM (
            order_id, product, current_stock, min_qty, target_qty,
            avg_daily_consumption, suggested_qty, confirmed_qty,
            supplier_available, supplier_price
        ) VALUES (
            %(order_id)s, %(product)s, %(current_stock)s, %(min_qty)s, %(target_qty)s,
            %(avg_daily)s, %(suggested_qty)s, %(confirmed_qty)s,
            %(supplier_available)s, %(supplier_price)s
        )
    """
    for item in items:
        cursor.execute(item_query, {
            'order_id':          order_id,
            'product':           item['id'],
            'current_stock':     item.get('closed_qty', 0),
            'min_qty':           item.get('min_qty', 0),
            'target_qty':        item.get('target_qty', 0),
            'avg_daily':         item.get('avg_daily_consumption', 0),
            'suggested_qty':     item.get('suggested_qty', 0),
            'confirmed_qty':     item.get('confirmed_qty', item.get('suggested_qty', 0)),
            'supplier_available': item.get('supplier_available'),
            'supplier_price':    item.get('supplier_price'),
        })

    return order_id
