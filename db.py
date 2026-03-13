import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD


def get_connection():
    """Return a new psycopg2 connection to QuantifiedStrides DB."""
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
