#!/usr/bin/env python3
"""Database initialization script for IntelliHostel.
Creates all required tables (students, complaints, common_issues, notifications, etc.)
and sets up initial admin credentials in PostgreSQL or SQLite.
"""
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database.create_db import main

if __name__ == "__main__":
    main()
