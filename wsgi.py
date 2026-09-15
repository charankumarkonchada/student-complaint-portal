"""
WSGI entrypoint for IntelliHostel production deployment.
Suitable for Gunicorn, uWSGI, or standard WSGI servers.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
