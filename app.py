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

    # Global Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

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