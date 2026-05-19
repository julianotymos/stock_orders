from typing import Dict, List
from datetime import datetime


def _parse_date(date_str: str) -> datetime:
    """Converte 'DD-MM-YYYY HH:MM:SS' para datetime."""
    try:
        return datetime.strptime(date_str, "%d-%m-%Y %H:%M:%S")
    except (ValueError, TypeError):
        return None


def save_supplier_orders(cursor, orders: List[Dict],
                         update_existing: bool = False) -> Dict[str, int]:
    """
    Salva pedidos da plataforma no banco.
    update_existing=True: atualiza status, total, service_note e nfe dos itens já existentes.
    Retorna {"inserted": N, "updated": N, "skipped": N}.
    """
    inserted = 0
    updated = 0
    skipped = 0

    for order in orders:
        platform_order_id = order.get("id")
        if not platform_order_id:
            continue

        total = _safe_decimal(order.get("total"))
        franchise_tax = _safe_decimal(order.get("franchise_tax"))
        vhsys = order.get("vhsys")

        product_invoice_value = None
        product_invoice_doc   = None
        service_invoice_value = None
        service_invoice_doc   = None

        for inv in order.get("invoices", []):
            chave = inv.get("f2_chvnfe", "") or ""
            valor = _safe_decimal(inv.get("f2_valfat"))
            doc   = inv.get("f2_doc")
            # chave NF-e de produtos tem 44 dígitos numéricos; NFS-e vem como UUID
            if len(chave.replace("-", "")) == 44 and chave.replace("-", "").isdigit():
                product_invoice_value = (product_invoice_value or 0) + (valor or 0) or None
                if product_invoice_doc is None:
                    product_invoice_doc = doc
            else:
                service_invoice_value = (service_invoice_value or 0) + (valor or 0) or None
                if service_invoice_doc is None:
                    service_invoice_doc = doc

        params = {
            'pid':     platform_order_id,
            'store':   order.get("store_id"),
            'pstatus': order.get("status"),
            'total':   total,
            'tax':     franchise_tax,
            'vhsys':   vhsys,
            'piv':     product_invoice_value,
            'pid_doc': product_invoice_doc,
            'siv':     service_invoice_value,
            'sid_doc': service_invoice_doc,
        }

        if update_existing:
            cursor.execute("""
                INSERT INTO SUPPLIER_ORDER (
                    platform_order_id, store_id, platform_status, total, franchise_tax,
                    vhsys, product_invoice_value, product_invoice_doc,
                    service_invoice_value, service_invoice_doc
                ) VALUES (
                    %(pid)s, %(store)s, %(pstatus)s, %(total)s, %(tax)s,
                    %(vhsys)s, %(piv)s, %(pid_doc)s, %(siv)s, %(sid_doc)s
                )
                ON CONFLICT (platform_order_id) DO UPDATE SET
                    platform_status       = EXCLUDED.platform_status,
                    total                 = EXCLUDED.total,
                    vhsys                 = COALESCE(EXCLUDED.vhsys, SUPPLIER_ORDER.vhsys),
                    product_invoice_value = COALESCE(EXCLUDED.product_invoice_value, SUPPLIER_ORDER.product_invoice_value),
                    product_invoice_doc   = COALESCE(EXCLUDED.product_invoice_doc,   SUPPLIER_ORDER.product_invoice_doc),
                    service_invoice_value = COALESCE(EXCLUDED.service_invoice_value, SUPPLIER_ORDER.service_invoice_value),
                    service_invoice_doc   = COALESCE(EXCLUDED.service_invoice_doc,   SUPPLIER_ORDER.service_invoice_doc)
                RETURNING id, (xmax = 0) AS is_new
            """, params)
        else:
            cursor.execute("""
                INSERT INTO SUPPLIER_ORDER (
                    platform_order_id, store_id, platform_status, total, franchise_tax,
                    vhsys, product_invoice_value, product_invoice_doc,
                    service_invoice_value, service_invoice_doc
                ) VALUES (
                    %(pid)s, %(store)s, %(pstatus)s, %(total)s, %(tax)s,
                    %(vhsys)s, %(piv)s, %(pid_doc)s, %(siv)s, %(sid_doc)s
                )
                ON CONFLICT (platform_order_id) DO NOTHING
                RETURNING id
            """, params)

        row = cursor.fetchone()
        if not row:
            skipped += 1
            continue

        order_db_id = row['id']
        is_new = row.get('is_new', True)

        if is_new:
            inserted += 1
        else:
            updated += 1

        if not is_new and not update_existing:
            continue

        if not is_new:
            # Atualiza apenas nfe/status nos itens existentes pelo platform_item_id
            for item in order.get("orderItems", []):
                cursor.execute("""
                    UPDATE SUPPLIER_ORDER_ITEM
                    SET nfe_bling_id       = COALESCE(%(nfe)s, nfe_bling_id),
                        sale_order_bling_id = COALESCE(%(sale)s, sale_order_bling_id)
                    WHERE order_id = %(oid)s AND platform_item_id = %(iid)s
                """, {
                    'nfe':  item.get("nfe_bling_id"),
                    'sale': item.get("sale_order_bling_id"),
                    'oid':  order_db_id,
                    'iid':  item.get("id"),
                })
            continue

        for item in order.get("orderItems", []):
            prod_info = item.get("products") or {}
            cat_info = prod_info.get("category") or {}
            item_date = _parse_date(item.get("created_at", ""))

            cursor.execute("""
                INSERT INTO SUPPLIER_ORDER_ITEM (
                    order_id, platform_item_id, external_product_id,
                    external_product_name, external_category,
                    quantity, price_unit, created_at,
                    nfe_bling_id, sale_order_bling_id
                ) VALUES (
                    %(order_id)s, %(item_id)s, %(ext_pid)s,
                    %(ext_name)s, %(ext_cat)s,
                    %(qty)s, %(price)s, %(dt)s,
                    %(nfe)s, %(sale_bling)s
                )
            """, {
                'order_id':   order_db_id,
                'item_id':    item.get("id"),
                'ext_pid':    item.get("product_id"),
                'ext_name':   prod_info.get("name", ""),
                'ext_cat':    cat_info.get("name", ""),
                'qty':        _safe_decimal(item.get("quantity")),
                'price':      _safe_decimal(item.get("price_unit")),
                'dt':         item_date,
                'nfe':        item.get("nfe_bling_id"),
                'sale_bling': item.get("sale_order_bling_id"),
            })

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def _safe_decimal(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None
