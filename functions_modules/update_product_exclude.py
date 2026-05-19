def set_product_exclude(cursor, product_id: int, exclude: bool, reason: str = None):
    """
    Adiciona ou remove um produto da tabela PRODUCT_EXCLUDE.
    exclude=True  → produto fora dos cálculos de consumo e pedido
    exclude=False → produto volta aos cálculos normalmente
    """
    if exclude:
        cursor.execute("""
            INSERT INTO PRODUCT_EXCLUDE (product_id, reason)
            VALUES (%(pid)s, %(reason)s)
            ON CONFLICT (product_id) DO UPDATE SET reason = EXCLUDED.reason
        """, {'pid': product_id, 'reason': reason})
    else:
        cursor.execute(
            "DELETE FROM PRODUCT_EXCLUDE WHERE product_id = %(pid)s",
            {'pid': product_id}
        )
    return cursor.rowcount
