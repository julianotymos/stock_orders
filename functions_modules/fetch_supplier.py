import os
import requests
from typing import List, Dict

SUPPLIER_API_URL = os.getenv('SUPPLIER_API_URL', '')
SUPPLIER_API_KEY = os.getenv('SUPPLIER_API_KEY', '')


def fetch_supplier_availability(product_ids: List[int]) -> Dict[int, dict]:
    """
    Consulta disponibilidade de produtos na API do fornecedor.
    Retorna: {product_id: {'available': bool | None, 'price': float | None}}

    Configure SUPPLIER_API_URL e SUPPLIER_API_KEY no arquivo .env.
    Se SUPPLIER_API_URL não estiver configurado, retorna disponibilidade como None
    para todos os produtos (modo não configurado).
    """
    if not SUPPLIER_API_URL:
        return {pid: {'available': None, 'price': None} for pid in product_ids}

    try:
        response = requests.post(
            f"{SUPPLIER_API_URL}/availability",
            json={'product_ids': product_ids},
            headers={
                'Authorization': f'Bearer {SUPPLIER_API_KEY}',
                'Content-Type':  'application/json',
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return {item['product_id']: item for item in data.get('products', [])}

    except requests.exceptions.Timeout:
        raise TimeoutError("API do fornecedor não respondeu no prazo de 15s.")
    except requests.exceptions.HTTPError as e:
        raise ConnectionError(
            f"Erro na API do fornecedor: HTTP {e.response.status_code} — {e.response.text[:200]}"
        )
    except Exception as e:
        raise ConnectionError(f"Erro ao consultar fornecedor: {e}")
