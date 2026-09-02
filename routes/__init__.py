"""Modular route blueprints registration for IntelliHostel.
Central integration maintained by K. Charankumar.
"""
from flask import url_for

# Team 1: R. Charan Kumar
from routes.charan.admin_login import admin_login_bp
from routes.charan.manage_complaints import manage_complaints_bp
from routes.charan.update_status import update_status_bp

# Team 2: K. Charankumar
from routes.charankumar.admin_dashboard import admin_dashboard_bp
from routes.charankumar.analytics import analytics_bp
from routes.charankumar.export_reports import export_reports_bp

# Team 3: B. Jagan
from routes.jagan.home import home_bp
from routes.jagan.add_complaint import add_complaint_bp
from routes.jagan.complaint_history import complaint_history_bp
from routes.jagan.view_complaint import view_complaint_bp

# Team 4: M. Raghunitha
from routes.raghunitha.register import register_bp
from routes.raghunitha.edit_complaint import edit_complaint_bp
from routes.raghunitha.profile import profile_bp

# Team 5: K. Deepthi
from routes.deepthi.login import login_bp
from routes.deepthi.forgot_password import forgot_password_bp
from routes.deepthi.verify_reset_otp import verify_reset_otp_bp
from routes.deepthi.reset_password import reset_password_bp
from routes.deepthi.change_password import change_password_bp
from routes.deepthi.notifications import notifications_bp

# Team 6: K. Vennela
from routes.vennela.student_dashboard import student_dashboard_bp
from routes.vennela.activity import activity_bp

ALL_BLUEPRINTS = [
    # Charan
    admin_login_bp,
    manage_complaints_bp,
    update_status_bp,
    # Charankumar
    admin_dashboard_bp,
    analytics_bp,
    export_reports_bp,
    # Jagan
    home_bp,
    add_complaint_bp,
    complaint_history_bp,
    view_complaint_bp,
    # Raghunitha
    register_bp,
    edit_complaint_bp,
    profile_bp,
    # Deepthi
    login_bp,
    forgot_password_bp,
    verify_reset_otp_bp,
    reset_password_bp,
    change_password_bp,
    notifications_bp,
    # Vennela
    student_dashboard_bp,
    activity_bp,
]

def register_blueprints(app):
    """Registers all 21 modular blueprints and configures global endpoint aliasing for url_for compatibility."""
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    def url_build_error_handler(error, endpoint, values):
        """Allows url_for('login') or url_for('dashboard') to resolve to modular blueprint endpoints."""
        for registered_endpoint in app.view_functions:
            if registered_endpoint.endswith("." + endpoint):
                return url_for(registered_endpoint, **values)
        raise error

    app.url_build_error_handlers.append(url_build_error_handler)
