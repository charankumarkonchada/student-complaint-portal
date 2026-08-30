import os
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

import config


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


class ConnectionAdapter:
    def __init__(self, conn):
        self.conn = conn

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
    if config.DATABASE_URL:
        if not psycopg2:
            raise RuntimeError(
                'psycopg2-binary is required for PostgreSQL.'
            )

        conn = psycopg2.connect(
            config.DATABASE_URL,
            sslmode=config.DB_SSLMODE,
            cursor_factory=RealDictCursor
        )

        conn.autocommit = False

        return ConnectionAdapter(conn)

    import sqlite3

    conn = sqlite3.connect(config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')

    return conn
