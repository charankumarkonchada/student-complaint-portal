import os
import logging
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

import config

logger = logging.getLogger(__name__)


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CursorAdapter:
    def __init__(self, cursor):
        self.cursor = cursor

    def _sql(self, sql):
        return sql.replace('?', '%s')

    def execute(self, sql, params=()):
        self.cursor.execute(self._sql(sql), params)
        return self

    def executemany(self, sql, seq):
        self.cursor.executemany(self._sql(sql), seq)
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        return Row(row) if isinstance(row, dict) else row

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [Row(r) if isinstance(r, dict) else r for r in rows]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def lastrowid(self):
        return getattr(self.cursor, 'lastrowid', None)

    @property
    def rowcount(self):
        return getattr(self.cursor, 'rowcount', -1)


class ConnectionAdapter:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql.replace('?', '%s'), params)
        return CursorAdapter(cur)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def get_db_connection():
    if config.DATABASE_URL and psycopg2:
        try:
            conn = psycopg2.connect(
                config.DATABASE_URL,
                sslmode=config.DB_SSLMODE,
                cursor_factory=RealDictCursor
            )
            conn.autocommit = False
            return ConnectionAdapter(conn)
        except Exception as e:
            logger.warning("PostgreSQL connection failed (%s). Falling back to SQLite.", e)

    import sqlite3

    # Connect with 30s lock timeout to prevent database locks under concurrent workers
    conn = sqlite3.connect(config.DATABASE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')

    try:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
    except Exception:
        pass

    return conn
