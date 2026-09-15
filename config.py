import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FLASK_DEBUG = os.environ.get('FLASK_DEBUG','0').lower() in {'1','true','yes'}
SECRET_KEY = os.environ.get('SECRET_KEY', '').strip()
if not SECRET_KEY or SECRET_KEY == 'change-me-in-production':
    if not FLASK_DEBUG and os.environ.get('TESTING', '').lower() not in {'1', 'true'}:
        import secrets
        import logging
        logging.getLogger("config").warning(
            "CRITICAL SECURITY ALERT: SECRET_KEY is unset or using default placeholder in production. "
            "Generating an ephemeral random secret key for this process. "
            "Please configure SECRET_KEY in your .env file."
        )
        SECRET_KEY = secrets.token_hex(32)
    else:
        SECRET_KEY = 'dev-secret-key-change-in-production'
DATABASE_URL = os.environ.get('DATABASE_URL','').strip()
DB_SSLMODE = os.environ.get('DB_SSLMODE','require')
DATABASE = os.path.join(BASE_DIR,'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR,'static','uploads')
MAX_CONTENT_LENGTH = 5*1024*1024
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','pdf'}
COLLEGE_NAME = os.environ.get('COLLEGE_NAME', 'RGUKT Ongole')
COLLEGE_DOMAIN = os.environ.get('COLLEGE_DOMAIN', '@rguktong.ac.in')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME','admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD','change-me')
SMTP_HOST = os.environ.get('SMTP_HOST','smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT','587'))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME','')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD','')
MAIL_FROM = os.environ.get('MAIL_FROM','') or SMTP_USERNAME
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS','1').lower() in {'1','true','yes','on'}
APP_BASE_URL = os.environ.get('APP_BASE_URL','http://127.0.0.1:5000').rstrip('/')
SUPABASE_URL = os.environ.get('SUPABASE_URL','').rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET','complaint-attachments')
OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES','10'))
OTP_MAX_ATTEMPTS = int(os.environ.get('OTP_MAX_ATTEMPTS','5'))

# Production Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '0').lower() in {'1', 'true', 'yes'} if FLASK_DEBUG else True
PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days

