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
            id_no TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            hostel TEXT,
            room_no TEXT,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS common_issues (
            id BIGSERIAL PRIMARY KEY,
            issue_code TEXT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            hostel TEXT NOT NULL,
            location_details TEXT,
            description TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending',
            assigned_to TEXT,
            admin_remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS complaints (
            id BIGSERIAL PRIMARY KEY,
            student_id BIGINT NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            common_issue_id BIGINT
                REFERENCES common_issues(id)
                ON DELETE SET NULL,
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
            is_archived INTEGER DEFAULT 0,
            archived_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS common_issue_notifications (
            id BIGSERIAL PRIMARY KEY,
            common_issue_id BIGINT NOT NULL
                REFERENCES common_issues(id)
                ON DELETE CASCADE,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS notification_reads (
            id BIGSERIAL PRIMARY KEY,
            common_issue_notification_id BIGINT NOT NULL
                REFERENCES common_issue_notifications(id)
                ON DELETE CASCADE,
            student_id BIGINT NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            is_archived INTEGER DEFAULT 0,
            archived_at TIMESTAMP,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(common_issue_notification_id, student_id)
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
        CREATE TABLE IF NOT EXISTS common_issue_history (
            id BIGSERIAL PRIMARY KEY,
            common_issue_id BIGINT NOT NULL
                REFERENCES common_issues(id)
                ON DELETE CASCADE,
            status TEXT NOT NULL,
            remarks TEXT,
            updated_by TEXT DEFAULT 'Hostel Administration',
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
            print("PostgreSQL statement failed:", error)
            raise

    migrate_postgresql(conn)


def create_sqlite_tables(conn):
    statements = [
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            id_no TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            hostel TEXT,
            room_no TEXT,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS common_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_code TEXT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            hostel TEXT NOT NULL,
            location_details TEXT,
            description TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending',
            assigned_to TEXT,
            admin_remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            common_issue_id INTEGER
                REFERENCES common_issues(id)
                ON DELETE SET NULL,
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
            is_archived INTEGER DEFAULT 0,
            archived_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS common_issue_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            common_issue_id INTEGER NOT NULL
                REFERENCES common_issues(id)
                ON DELETE CASCADE,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS notification_reads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            common_issue_notification_id INTEGER NOT NULL
                REFERENCES common_issue_notifications(id)
                ON DELETE CASCADE,
            student_id INTEGER NOT NULL
                REFERENCES students(id)
                ON DELETE CASCADE,
            is_archived INTEGER DEFAULT 0,
            archived_at TIMESTAMP,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(common_issue_notification_id, student_id)
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
        CREATE TABLE IF NOT EXISTS common_issue_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            common_issue_id INTEGER NOT NULL
                REFERENCES common_issues(id)
                ON DELETE CASCADE,
            status TEXT NOT NULL,
            remarks TEXT,
            updated_by TEXT DEFAULT 'Hostel Administration',
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
    migrate_sqlite(conn)


def migrate_sqlite(conn):
    """Safely adds new columns and indexes to existing SQLite databases."""
    cursor = conn.execute("PRAGMA table_info(complaints)")
    columns = [row[1] for row in cursor.fetchall()]

    if "common_issue_id" not in columns:
        conn.execute("ALTER TABLE complaints ADD COLUMN common_issue_id INTEGER REFERENCES common_issues(id) ON DELETE SET NULL")
        conn.commit()

    ci_cursor = conn.execute("PRAGMA table_info(common_issues)")
    ci_columns = [row[1] for row in ci_cursor.fetchall()]
    if "issue_code" not in ci_columns:
        try:
            conn.execute("ALTER TABLE common_issues ADD COLUMN issue_code TEXT")
            conn.commit()
        except Exception:
            pass

    # Safe column migrations for notifications and notification_reads archiving
    notif_cursor = conn.execute("PRAGMA table_info(notifications)")
    notif_cols = [row[1] for row in notif_cursor.fetchall()]
    if "is_archived" not in notif_cols:
        try:
            conn.execute("ALTER TABLE notifications ADD COLUMN is_archived INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE notifications ADD COLUMN archived_at TIMESTAMP")
            conn.commit()
        except Exception:
            pass

    nr_cursor = conn.execute("PRAGMA table_info(notification_reads)")
    nr_cols = [row[1] for row in nr_cursor.fetchall()]
    if "is_archived" not in nr_cols:
        try:
            conn.execute("ALTER TABLE notification_reads ADD COLUMN is_archived INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE notification_reads ADD COLUMN archived_at TIMESTAMP")
            conn.commit()
        except Exception:
            pass

    # Create performance indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_complaints_common_issue ON complaints(common_issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_common_issues_status_hostel ON common_issues(status, hostel)",
        "CREATE INDEX IF NOT EXISTS idx_common_issue_notifications_issue ON common_issue_notifications(common_issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_notification_reads_lookup ON notification_reads(student_id, common_issue_notification_id)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_student_archived ON notifications(student_id, is_archived, is_read)",
        "CREATE INDEX IF NOT EXISTS idx_notification_reads_archived ON notification_reads(student_id, is_archived)"
    ]
    for idx in indexes:
        try:
            conn.execute(idx)
        except Exception:
            pass
    conn.commit()

    # Backfill missing issue_code values
    try:
        issues_without_code = conn.execute("SELECT id FROM common_issues WHERE issue_code IS NULL OR issue_code = ''").fetchall()
        for iwc in issues_without_code:
            conn.execute("UPDATE common_issues SET issue_code = ? WHERE id = ?", (f"CI-{iwc['id']:03d}", iwc["id"]))
        conn.commit()
    except Exception:
        pass


def migrate_postgresql(conn):
    """Safely adds new columns and indexes to existing PostgreSQL databases."""
    try:
        cur = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'complaints' AND column_name = 'common_issue_id'
            """
        )
        if not cur.fetchone():
            conn.execute("ALTER TABLE complaints ADD COLUMN common_issue_id BIGINT REFERENCES common_issues(id) ON DELETE SET NULL")
            conn.commit()

        ci_cur = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'common_issues' AND column_name = 'issue_code'
            """
        )
        if not ci_cur.fetchone():
            conn.execute("ALTER TABLE common_issues ADD COLUMN issue_code TEXT")
            conn.commit()

        notif_cur = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'notifications' AND column_name = 'is_archived'
            """
        )
        if not notif_cur.fetchone():
            conn.execute("ALTER TABLE notifications ADD COLUMN is_archived INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE notifications ADD COLUMN archived_at TIMESTAMP")
            conn.commit()

        nr_cur = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'notification_reads' AND column_name = 'is_archived'
            """
        )
        if not nr_cur.fetchone():
            conn.execute("ALTER TABLE notification_reads ADD COLUMN is_archived INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE notification_reads ADD COLUMN archived_at TIMESTAMP")
            conn.commit()

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_complaints_common_issue ON complaints(common_issue_id)",
            "CREATE INDEX IF NOT EXISTS idx_common_issues_status_hostel ON common_issues(status, hostel)",
            "CREATE INDEX IF NOT EXISTS idx_common_issue_notifications_issue ON common_issue_notifications(common_issue_id)",
            "CREATE INDEX IF NOT EXISTS idx_notification_reads_lookup ON notification_reads(student_id, common_issue_notification_id)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_student_archived ON notifications(student_id, is_archived, is_read)",
            "CREATE INDEX IF NOT EXISTS idx_notification_reads_archived ON notification_reads(student_id, is_archived)"
        ]
        for idx in indexes:
            try:
                conn.execute(idx)
                conn.commit()
            except Exception:
                conn.rollback()

        # Backfill missing issue_code values
        try:
            issues_without_code = conn.execute("SELECT id FROM common_issues WHERE issue_code IS NULL OR issue_code = ''").fetchall()
            for iwc in issues_without_code:
                conn.execute("UPDATE common_issues SET issue_code = ? WHERE id = ?", (f"CI-{iwc['id']:03d}", iwc["id"]))
            conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("PostgreSQL migration notice:", e)


def create_admin(conn):
    admin = conn.execute(
        "SELECT id FROM admin LIMIT 1"
    ).fetchone()

    if admin is None and config.ADMIN_USERNAME and config.ADMIN_PASSWORD and config.ADMIN_PASSWORD not in {"change-me", "change-to-a-strong-admin-password-here"}:
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
        from database.db import ConnectionAdapter
        if isinstance(conn, ConnectionAdapter):
            create_postgresql_tables(conn)
            create_admin(conn)
            print("Database initialized: PostgreSQL cloud with Common Issues support")
        else:
            create_sqlite_tables(conn)
            create_admin(conn)
            print("Database initialized: SQLite with Common Issues support")

    finally:
        conn.close()


if __name__ == "__main__":
    main()