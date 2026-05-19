from typing import Optional


def create_product(cursor, product_name: str, description: str, product_type: str,
                   product_size: Optional[str] = None,
                   sort_order: Optional[int] = None,
                   system_user: int = 1) -> int:
    """Insere um novo produto ativo e retorna o ID gerado."""
    cursor.execute("""
        INSERT INTO PRODUCT (product_name, description, product_type, status, product_size, sort_order, system_user)
        VALUES (%(product_name)s, %(description)s, %(product_type)s, 1, %(product_size)s, %(sort_order)s, %(system_user)s)
        RETURNING id
    """, {
        'product_name': product_name.strip(),
        'description':  description.strip(),
        'product_type': product_type,
        'product_size': product_size.strip() if product_size else None,
        'sort_order':   sort_order,
        'system_user':  system_user,
    })
    return cursor.fetchone()['id']
