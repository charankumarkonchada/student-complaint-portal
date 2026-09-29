"""Database module for IntelliHostel."""
from backend.database.db import get_db_connection
from backend.database.queries import init_database

__all__ = ["get_db_connection", "init_database"]
