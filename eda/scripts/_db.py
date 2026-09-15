"""EDA용 DB 연결 헬퍼. 저장소 루트 .env의 DATABASE_READONLY_URL만 사용한다."""
import os

import psycopg2
import psycopg2.extras


def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return env


def get_connection():
    env = _load_env()
    conn = psycopg2.connect(env["DATABASE_READONLY_URL"])
    conn.set_session(readonly=True)
    return conn


def query_df(sql, params=None):
    import pandas as pd

    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()
