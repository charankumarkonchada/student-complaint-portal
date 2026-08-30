"""Routes package for IntelliHostel."""
from flask import Blueprint, url_for

main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__)
dashboard_bp = Blueprint("dashboard", __name__)
complaints_bp = Blueprint("complaints", __name__)
admin_bp = Blueprint("admin", __name__)

# Import route handlers to attach them to blueprints
from routes import main
from routes import auth
from routes import dashboard
from routes import complaints
from routes import admin

def register_blueprints(app):
    """Registers all blueprints and configures global endpoint aliasing for url_for compatibility."""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(admin_bp)

    def url_build_error_handler(error, endpoint, values):
        """Allows url_for('login') or url_for('dashboard') to resolve to blueprint endpoints."""
        for registered_endpoint in app.view_functions:
            if registered_endpoint.endswith("." + endpoint):
                return url_for(registered_endpoint, **values)
        raise error

    app.url_build_error_handlers.append(url_build_error_handler)
