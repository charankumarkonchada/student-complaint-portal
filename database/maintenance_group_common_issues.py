"""Explicit maintenance command for optional historical Common Issue grouping.

This is intentionally NOT imported by create_app() so application startup remains fast.
Run it manually after reviewing backups and database size.
"""
from database.db import get_db_connection
from services.common_issue_service import group_existing_duplicate_complaints

if __name__ == "__main__":
    conn = get_db_connection()
    try:
        result = group_existing_duplicate_complaints(conn)
        conn.commit()
        print(f"Historical grouping completed: {result}")
    finally:
        conn.close()
