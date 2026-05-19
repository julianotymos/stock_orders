import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

config = {
    'dbname':   os.getenv('DB_NAME',  'postgres'),
    'user':     os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host':     os.getenv('DB_HOST'),
    'port':     os.getenv('DB_PORT', '6543'),
    'cursor_factory': RealDictCursor,
}


def get_db_connection():
    try:
        return psycopg2.connect(**config)
    except Exception as e:
        raise ConnectionError(f"Erro ao conectar ao banco de dados: {e}")
