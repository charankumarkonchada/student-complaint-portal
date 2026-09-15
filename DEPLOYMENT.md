# IntelliHostel — Production Deployment & Operations Guide

This guide provides step-by-step instructions for deploying the **IntelliHostel Student Complaint Portal** to production environments.

---

## 1. Architectural Overview

IntelliHostel is a modular, high-scale Flask application designed for university hostel environments:

- **WSGI Server**: [Gunicorn](https://gunicorn.org/) (configured in `gunicorn.conf.py` and invoked via `wsgi.py`).
- **Web Framework**: Flask 3.1 with blueprint-based modular routing across 6 team member submodules.
- **Database Engine**: PostgreSQL (Supabase pooler / AWS RDS / Neon / Railway) with automatic fallback to local SQLite for isolated setups.
- **Master Issue Scalability Engine**: Groups 1,000+ duplicate student complaints into single Master Common Issues; single administrative actions propagate across all tickets in $O(1)$ set-based SQL queries.
- **File Storage**: Supabase Cloud Storage bucket with local fallback to `static/uploads/`.
- **Email Delivery**: SMTP via TLS for password reset OTPs and system notifications.

---

## 2. Environment Configuration

1. Copy the template:
   ```bash
   cp .env.example .env
   ```

2. Generate a cryptographically secure `SECRET_KEY`:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Populate `.env` with your production values:
   ```ini
   SECRET_KEY=your_generated_64_character_hex_key
   FLASK_DEBUG=0
   PORT=5000
   APP_BASE_URL=https://complaints.rguktong.ac.in
   SESSION_COOKIE_SECURE=1

   # PostgreSQL connection string
   DATABASE_URL=postgresql://postgres.xxx:password@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
   DB_SSLMODE=require

   # Institution bounds
   COLLEGE_NAME=Rajiv Gandhi University of Knowledge Technologies - Ongole
   COLLEGE_DOMAIN=@rguktong.ac.in

   # Master admin credentials
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=SetAStrongPasswordHere2026!

   # SMTP settings
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=hostel.complaints@rguktong.ac.in
   SMTP_PASSWORD=your_16_char_google_app_password
   MAIL_FROM="IntelliHostel RGUKT <hostel.complaints@rguktong.ac.in>"
   SMTP_USE_TLS=1

   # Supabase Storage (Optional)
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJh...
   SUPABASE_STORAGE_BUCKET=complaint-attachments
   ```

---

## 3. Option A — Docker & Docker Compose (Recommended)

Docker provides a standardized container environment ensuring that all native libraries and dependencies match across development, staging, and production.

### Step 1: Build and Launch Containers
```bash
docker compose up -d --build
```

### Step 2: Verify Running Services
```bash
docker compose ps
docker compose logs -f web
```

### Step 3: Run Database Schema Initialization (First Run Only)
```bash
docker compose exec web python3 database/create_db.py
```

The web service is automatically exposed at `http://localhost:5000` with an active healthcheck.

---

## 4. Option B — PaaS Deployment (Render / Railway / Heroku)

### Deploying to Render:
1. Create a new **Web Service** on [Render Dashboard](https://dashboard.render.com).
2. Connect your GitHub repository.
3. Configure the service:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `gunicorn -c gunicorn.conf.py wsgi:app`
4. Add all environment variables from `.env` in the **Environment** tab.
5. Deploy!

### Deploying to Railway:
1. Create a new project on [Railway](https://railway.app).
2. Deploy from GitHub repository.
3. Railway automatically detects `Procfile` (`web: gunicorn -c gunicorn.conf.py wsgi:app`).
4. Under **Variables**, add all required keys from `.env`.

---

## 5. Option C — Traditional VPS (Ubuntu / Debian + Nginx + Systemd)

For dedicated on-premise university servers or AWS EC2 / DigitalOcean Droplets:

### Step 1: Install System Packages
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx libpq-dev build-essential
```

### Step 2: Clone and Setup Virtual Environment
```bash
cd /var/www
sudo git clone <REPO_URL> intellihostel
cd intellihostel
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env  # configure production credentials
python3 database/create_db.py
```

### Step 3: Configure Systemd Service
Create `/etc/systemd/system/intellihostel.service`:
```ini
[Unit]
Description=IntelliHostel Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/intellihostel
Environment="PATH=/var/www/intellihostel/.venv/bin"
ExecStart=/var/www/intellihostel/.venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo chown -R www-data:www-data /var/www/intellihostel
sudo systemctl daemon-reload
sudo systemctl enable --now intellihostel
sudo systemctl status intellihostel
```

### Step 4: Configure Nginx Reverse Proxy
Create `/etc/nginx/sites-available/intellihostel`:
```nginx
server {
    server_name complaints.rguktong.ac.in;

    client_max_body_size 10M;

    location /static/ {
        alias /var/www/intellihostel/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Enable site and configure SSL:
```bash
sudo ln -s /etc/nginx/sites-available/intellihostel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d complaints.rguktong.ac.in
```

---

## 6. Verification and Smoke Testing

After deployment, verify that all core capabilities operate as expected:

1. **Health Check**:
   ```bash
   curl -I https://complaints.rguktong.ac.in/
   ```
   Should return `HTTP/1.1 200 OK` or `302 Found`.

2. **Automated Test Suite**:
   Run the 9-scenario regression suite:
   ```bash
   python3 tests/test_common_issues.py
   ```
   Ensures all 8 tests for master issue grouping, single-action propagation, student privacy, and existing routes pass.

3. **Master Issue Single-Action Verification**:
   - Log into `/admin_login` as Master Administrator.
   - Navigate to **Shared / Common Issues** (`/admin/common_issues`).
   - Select an issue and click **Update Once & Propagate to All**.
   - Verify all student tickets update instantaneously in a single SQL operation.

---

## 7. Security Hardening Checklist

- [x] `FLASK_DEBUG=0` in production.
- [x] Cryptographically random `SECRET_KEY` generated.
- [x] HTTPS enforced with `SESSION_COOKIE_SECURE=1`.
- [x] Session cookie flags: `HttpOnly=True` and `SameSite=Lax`.
- [x] Rate limiting and OTP brute-force limits active (`OTP_MAX_ATTEMPTS=5`).
- [x] Student domain strictly bounded to `@rguktong.ac.in`.
- [x] Privacy architecture prevents leaking student identities across shared issues.
- [x] File upload size capped at 5MB (`MAX_CONTENT_LENGTH`).
