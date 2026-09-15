import os
from flask import Flask, render_template

import config
from database.queries import init_database, unread_count
from routes import register_blueprints

def create_app():
    """Application factory for IntelliHostel Flask application."""
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        UPLOAD_FOLDER=config.UPLOAD_FOLDER,
        MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
        ALLOWED_EXTENSIONS=config.ALLOWED_EXTENSIONS,
        SESSION_COOKIE_HTTPONLY=config.SESSION_COOKIE_HTTPONLY,
        SESSION_COOKIE_SAMESITE=config.SESSION_COOKIE_SAMESITE,
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=config.PERMANENT_SESSION_LIFETIME,
    )

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize database schema
    init_database()

    # Context processor for global template variables
    @app.context_processor
    def inject_globals():
        return {
            "unread_notifications": unread_count(),
            "college_name": config.COLLEGE_NAME,
            "current_year": 2026
        }

    # Global Error Handlers (Member-owned templates: Charan 404, Vennela 500)
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("charan/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server exception: %s", e)
        return render_template("vennela/500.html"), 500

    # Production HTTP Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Reverse proxy header trust (Nginx / PaaS / Load Balancers)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Register all modular route blueprints
    register_blueprints(app)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=config.FLASK_DEBUG
    )