# app/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

SCHEMA = os.getenv("PG_SCHEMA", "inv")  # 👈 importante que exista esta línea

def get_conn():
    conn = psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", 5432)),
        dbname=os.getenv("PG_DB", "tsp_inventory"),
        user=os.getenv("PG_USER", "tsp_app"),
        password=os.getenv("PG_PASSWORD", "1234"),
    )
    return conn

def fetch_all(sql, params=None):
    with get_conn() as cn:
        with cn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()

def fetch_one(sql, params=None):
    with get_conn() as cn:
        with cn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or {})
            row = cur.fetchone()
            return row
