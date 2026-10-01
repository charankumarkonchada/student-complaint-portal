import os
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import jinja2
from backend.services.csrf_service import get_csrf_token, validate_csrf_token

import backend.config as config
from backend.database.queries import init_database, unread_count
from backend.routes import register_blueprints

ADMIN_BLUEPRINTS = {
    "admin_dashboard",
    "manage_complaints",
    "update_status",
    "common_issues",
    "student_id_requests",
    "analytics",
    "export_reports",
}

STUDENT_BLUEPRINTS = {
    "student_dashboard",
    "add_complaint",
    "complaint_history",
    "view_complaint",
    "edit_complaint",
    "profile",
    "change_password",
    "notifications",
    "activity",
}

PUBLIC_ENDPOINTS = {
    "static",
    "home.home",
    "login.login",
    "register.register",
    "admin_login.admin_login",
    "forgot_password.forgot_password",
    "verify_reset_otp.verify_reset_otp",
    "reset_password.reset_password",
}


def create_app():
    """Application factory for IntelliHostel Flask application."""
    project_root = Path(__file__).resolve().parent.parent
    template_folder = project_root / "frontend" / "templates"
    static_folder = project_root / "frontend" / "static"

    app = Flask(
        __name__,
        root_path=str(project_root),
        template_folder=str(template_folder),
        static_folder=str(static_folder)
    )

    # Multi-path Jinja loader to guarantee reliable template discovery across environments
    template_search_paths = [
        str(template_folder),
        str(Path.cwd() / "frontend" / "templates"),
        str(Path("/var/task") / "frontend" / "templates"),
    ]
    unique_paths = []
    for p in template_search_paths:
        if p not in unique_paths and os.path.isdir(p):
            unique_paths.append(p)
    if not unique_paths:
        unique_paths.append(str(template_folder))

    app.jinja_loader = jinja2.FileSystemLoader(unique_paths)

    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        UPLOAD_FOLDER=config.UPLOAD_FOLDER,
        MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
        ALLOWED_EXTENSIONS=config.ALLOWED_EXTENSIONS,
        SESSION_COOKIE_HTTPONLY=config.SESSION_COOKIE_HTTPONLY,
        SESSION_COOKIE_SAMESITE=config.SESSION_COOKIE_SAMESITE,
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=config.PERMANENT_SESSION_LIFETIME,
        TESTING=os.environ.get("TESTING", "0").lower() in {"1", "true", "yes"},
        APP_ENV=config.APP_ENV,
        APP_BASE_URL=config.APP_BASE_URL,
        WTF_CSRF_ENABLED=True,
    )

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # CSRF & Route Authorization protection for all requests
    @app.before_request
    def enforce_security_and_auth():
        # Centralized route authorization check
        if request.blueprint in ADMIN_BLUEPRINTS:
            if not session.get("admin"):
                if request.path.startswith("/api/") or request.is_json:
                    return jsonify({"error": "Unauthorized"}), 401
                return redirect(url_for("admin_login.admin_login"))
        elif request.blueprint in STUDENT_BLUEPRINTS:
            if not session.get("student_id"):
                if request.path.startswith("/api/") or request.is_json:
                    return jsonify({"error": "Unauthorized"}), 401
                return redirect(url_for("login.login"))

        # CSRF protection for all state-changing requests. Tests may disable explicitly.
        if app.config.get("TESTING") and not app.config.get("WTF_CSRF_ENABLED", True):
            return None
        validate_csrf_token()

    @app.context_processor
    def inject_security_globals():
        return {"csrf_token": get_csrf_token}

    @app.context_processor
    def inject_auth_state():
        is_auth = False
        user_type = None
        if request.blueprint in ADMIN_BLUEPRINTS and session.get("admin"):
            is_auth = True
            user_type = "admin"
        elif request.blueprint in STUDENT_BLUEPRINTS and session.get("student_id"):
            is_auth = True
            user_type = "student"
        return {
            "is_authenticated_page": is_auth,
            "auth_user_type": user_type,
        }

    # Lightweight session verification endpoint for BFCache / Multi-tab validation
    @app.route("/api/auth/status", methods=["GET"])
    def auth_status():
        if session.get("admin"):
            return jsonify({"authenticated": True, "role": "admin"})
        elif session.get("student_id"):
            return jsonify({"authenticated": True, "role": "student"})
        return jsonify({"authenticated": False}), 401

    # Initialize database schema
    init_database()

    # Context processor for global template variables
    @app.context_processor
    def inject_globals():
        return {
            "unread_notifications": unread_count(),
            "college_name": config.COLLEGE_NAME,
            "current_year": __import__("datetime").datetime.now().year
        }

    # Global Error Handlers (Categorized in frontend/templates/errors/)
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server exception: %s", e)
        return render_template("errors/500.html"), 500

    # Production HTTP Security & Cache-Control Headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if config.IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Centralized no-cache headers for authenticated student and admin responses and logout responses
        is_auth_route = request.blueprint in ADMIN_BLUEPRINTS or request.blueprint in STUDENT_BLUEPRINTS
        is_logout_route = request.endpoint in {"login.logout", "admin_login.admin_logout"}
        is_auth_session = bool(session.get("student_id") or session.get("admin"))
        is_static = request.endpoint == "static" or (request.path and request.path.startswith("/static/"))
        is_public = request.endpoint in PUBLIC_ENDPOINTS or request.path == "/"

        if not is_static and (is_auth_route or is_logout_route or request.endpoint == "auth_status" or (is_auth_session and not is_public)):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    # Reverse proxy header trust (Nginx / PaaS / Load Balancers)
    from werkzeug.middleware.proxy_fix import ProxyFix
    if config.IS_PRODUCTION:
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
