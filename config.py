import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG','0').lower() in {'1','true','yes'}
DATABASE_URL = os.environ.get('DATABASE_URL','').strip()
DB_SSLMODE = os.environ.get('DB_SSLMODE','require')
DATABASE = os.path.join(BASE_DIR,'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR,'static','uploads')
MAX_CONTENT_LENGTH = 5*1024*1024
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','pdf'}
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
