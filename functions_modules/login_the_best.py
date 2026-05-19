import os
import requests
from dotenv import load_dotenv

load_dotenv()


def login_the_best(username: str = None, password: str = None) -> str | None:
    """
    Faz login na plataforma The Best e retorna o access_token JWT.
    Credenciais lidas de PLATFORM_USERNAME / PLATFORM_PASSWORD no .env.
    """
    if username is None:
        username = os.getenv("PLATFORM_USERNAME", "")
    if password is None:
        password = os.getenv("PLATFORM_PASSWORD", "")

    if not username or not password:
        raise ValueError("PLATFORM_USERNAME e PLATFORM_PASSWORD devem estar configurados no .env")

    url = "https://amatech-prd.azure-api.net/api/janus/user/login"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://franqueadosthebest.com",
        "Referer": "https://franqueadosthebest.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
    }

    resp = requests.post(url, headers=headers, json={"username": username, "password": password}, timeout=15)

    if resp.status_code == 201:
        return resp.json().get("access_token")

    raise ValueError(f"Login falhou (HTTP {resp.status_code}): {resp.text[:200]}")
