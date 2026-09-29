import hmac
import secrets
from flask import session, request, abort

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SESSION_KEY = "_csrf_token"

def get_csrf_token():
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token

def validate_csrf_token():
    if request.method in SAFE_METHODS:
        return
    expected = session.get(SESSION_KEY)
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        abort(400, description="Invalid or missing CSRF token.")

def rotate_csrf_token():
    session.pop(SESSION_KEY, None)
    return get_csrf_token()
