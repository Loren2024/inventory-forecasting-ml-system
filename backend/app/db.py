# app/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "tsp_inventory"),
        user=os.getenv("DB_USER", "tsp_app"),
        password=os.getenv("DB_PASSWORD", "1234")
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
