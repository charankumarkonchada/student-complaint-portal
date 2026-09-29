"""WSGI entrypoint for IntelliHostel production deployment.
Suitable for Gunicorn, uWSGI, or standard WSGI servers.
"""
from backend.app import app, create_app

if __name__ == "__main__":
    app.run()
