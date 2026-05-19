def upsert_stock_minimum(cursor, product_id: int, min_qty: int, target_qty: int, period_days: int = 30):
    """Insere ou atualiza configuração de estoque mínimo para um produto."""
    query = """
        INSERT INTO STOCK_MINIMUM (product, min_qty, target_qty, period_days, updated_at)
        VALUES (%(product_id)s, %(min_qty)s, %(target_qty)s, %(period_days)s, CURRENT_TIMESTAMP)
        ON CONFLICT (product) DO UPDATE
        SET min_qty     = EXCLUDED.min_qty,
            target_qty  = EXCLUDED.target_qty,
            period_days = EXCLUDED.period_days,
            updated_at  = CURRENT_TIMESTAMP
    """
    cursor.execute(query, {
        'product_id':  product_id,
        'min_qty':     min_qty,
        'target_qty':  target_qty,
        'period_days': period_days,
    })
    return cursor.rowcount
