def update_product_status(cursor, product_id: int, status_id: int) -> int:
    """
    Atualiza o status de um produto (1 = ativo, 2 = inativo).
    Altera apenas a coluna status da tabela PRODUCT existente.
    """
    query = """
        UPDATE PRODUCT
        SET status    = %(status_id)s
        WHERE id      = %(product_id)s
    """
    cursor.execute(query, {'status_id': status_id, 'product_id': product_id})
    return cursor.rowcount
