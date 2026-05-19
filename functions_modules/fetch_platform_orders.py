import os
import requests
from typing import List, Dict
from dotenv import load_dotenv
from functions_modules.login_the_best import login_the_best

load_dotenv()

PLATFORM_STORE_ID = os.getenv("PLATFORM_STORE_ID", "467")
PLATFORM_BASE_URL = "https://amatech-prd.azure-api.net/api/odin"


def _get_token() -> str:
    """Obtém token fazendo login. Lança ValueError se falhar."""
    token = login_the_best()
    if not token:
        raise ValueError("Não foi possível obter token de acesso. Verifique PLATFORM_USERNAME e PLATFORM_PASSWORD no .env")
    return token


def fetch_platform_orders(page: int = 1, size: int = 30, type_of_load: int = 0,
                          token: str = None) -> Dict:
    """
    Busca pedidos da plataforma The Best (amatech).
    Retorna o JSON bruto com 'content' e metadados de paginação.
    """
    if token is None:
        token = _get_token()

    url = f"{PLATFORM_BASE_URL}/orders"
    params = {
        "stores_ids": PLATFORM_STORE_ID,
        "page": page,
        "size": size,
        "type_of_load": type_of_load,
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_all_platform_orders(max_pages: int = 10) -> List[Dict]:
    """
    Busca todas as páginas de pedidos até max_pages.
    Faz login uma única vez e reutiliza o token em todas as páginas.
    """
    token = _get_token()
    all_orders = []
    for page in range(1, max_pages + 1):
        data = fetch_platform_orders(page=page, size=50, token=token)
        content = data.get("content", [])
        if not content:
            break
        all_orders.extend(content)
        total_pages = data.get("totalPages") or data.get("total_pages")
        if total_pages and page >= total_pages:
            break
    return all_orders


def extract_products_from_orders(orders: List[Dict]) -> Dict[int, str]:
    """
    Extrai mapa {external_product_id: product_name} de todos os itens dos pedidos.
    Útil para popular PRODUCT_MAPPING.
    """
    products: Dict[int, str] = {}
    for order in orders:
        for item in order.get("orderItems", []):
            pid = item.get("product_id")
            name = (item.get("products") or {}).get("name", "")
            if pid and pid not in products:
                products[pid] = name
    return products
