"""Application entry point for IntelliHostel.

Provides direct compatibility for Vercel Serverless, Gunicorn, and local execution.
Delegates to backend application factory in backend/app.py.
"""
from backend.app import app, create_app

if __name__ == "__main__":
    from backend.config import FLASK_DEBUG
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=FLASK_DEBUG
    )