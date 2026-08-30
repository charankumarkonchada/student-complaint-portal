import os
import sys
from werkzeug.security import generate_password_hash

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import config
from database.db import get_db_connection


def create_postgresql_tables(conn):
    statements = [
        """
        CREATE TABLE IF NOT EXISTS students (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            hostel TEXT,
            room_no TEXT,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS complaints (
            id BIGSERIAL PRIMARY KEY,
            student_id BIGINT NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            category TEXT,
            title TEXT,
            description TEXT,
            image TEXT,
            priority TEXT,
            status TEXT DEFAULT 'Pending',
            assigned_to TEXT,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ai_category TEXT,
            ai_category_confidence DOUBLE PRECISION,
            ai_priority TEXT,
            ai_priority_confidence DOUBLE PRECISION,
            ai_resolution_days DOUBLE PRECISION,
            ai_duplicate_id BIGINT,
            ai_duplicate_similarity DOUBLE PRECISION
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS notifications (
            id BIGSERIAL PRIMARY KEY,
            student_id BIGINT NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS complaint_history (
            id BIGSERIAL PRIMARY KEY,
            complaint_id BIGINT NOT NULL
                REFERENCES complaints(id)
                ON DELETE CASCADE,
            status TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id BIGSERIAL PRIMARY KEY,
            student_id BIGINT NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            otp_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            attempts INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS admin (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    ]

    for statement in statements:
        try:
            conn.execute(statement)
            conn.commit()
        except Exception as error:
            conn.rollback()
            print("Database statement failed:")
            print(error)
            raise


def create_sqlite_tables(conn):
    statements = [
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            hostel TEXT,
            room_no TEXT,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            category TEXT,
            title TEXT,
            description TEXT,
            image TEXT,
            priority TEXT,
            status TEXT DEFAULT 'Pending',
            assigned_to TEXT,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ai_category TEXT,
            ai_category_confidence REAL,
            ai_priority TEXT,
            ai_priority_confidence REAL,
            ai_resolution_days REAL,
            ai_duplicate_id INTEGER,
            ai_duplicate_similarity REAL
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS complaint_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL
                REFERENCES complaints(id)
                ON DELETE CASCADE,
            status TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            otp_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            attempts INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    ]

    for statement in statements:
        conn.execute(statement)

    conn.commit()


def create_admin(conn):
    admin = conn.execute(
        "SELECT id FROM admin LIMIT 1"
    ).fetchone()

    if admin is None:
        conn.execute(
            """
            INSERT INTO admin(username, password)
            VALUES(?, ?)
            """,
            (
                config.ADMIN_USERNAME,
                generate_password_hash(
                    config.ADMIN_PASSWORD
                )
            )
        )
        conn.commit()


def main():
    conn = get_db_connection()

    try:
        if config.DATABASE_URL:
            create_postgresql_tables(conn)
            create_admin(conn)
            print("Database initialized: PostgreSQL cloud")
        else:
            create_sqlite_tables(conn)
            create_admin(conn)
            print("Database initialized: SQLite")

    finally:
        conn.close()


if __name__ == "__main__":
    main()