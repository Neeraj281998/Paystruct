"""Database connection settings from the environment. The password is never printed or written anywhere."""
from __future__ import annotations

import os
from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def dsn() -> str | None:
    """PAYSTRUCT_DB_URL, or built from POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_PORT (the docker-compose variables)."""
    url = os.environ.get("PAYSTRUCT_DB_URL")
    if url:
        return url
    user, pw, db = os.environ.get("POSTGRES_USER"), os.environ.get("POSTGRES_PASSWORD"), os.environ.get("POSTGRES_DB")
    if not (user and pw and db):
        return None
    return f"postgresql://{user}:{pw}@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}/{db}"


def connect(search_path: str | None = None, autocommit: bool = True):
    import psycopg
    d = dsn()
    if d is None:
        raise RuntimeError("no database settings in the environment (PAYSTRUCT_DB_URL or POSTGRES_USER/PASSWORD/DB)")
    kwargs = {"options": f"-csearch_path={search_path}"} if search_path else {}
    return psycopg.connect(d, autocommit=autocommit, **kwargs)


def apply_schema(conn) -> None:
    """Idempotent: CREATE TABLE IF NOT EXISTS only."""
    conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    with connect() as c:
        apply_schema(c)
    print("agent schema applied (idempotent)")
