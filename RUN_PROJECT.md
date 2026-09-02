# How to Run IntelliHostel Locally

This document provides exact, verified instructions to set up, configure, initialize, and run the **IntelliHostel Student Complaint Portal** on your local machine.

---

## 1. Prerequisites
- **Python:** Python 3.10, 3.11, 3.12, or 3.13
- **Git:** Git 2.20 or newer
- **Operating System:** Linux, macOS, or Windows (WSL recommended on Windows)

---

## 2. Step-by-Step Installation

### Step 1: Clone the Repository
```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SE
```

### Step 2: Create and Activate a Virtual Environment
```bash
# On Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# On Windows (Command Prompt):
python -m venv .venv
.venv\Scripts\activate.bat

# On Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install Required Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Environment Configuration (`.env`)

Copy the provided environment template to `.env`:

```bash
cp .env.example .env
```

Open `.env` in your editor and configure according to your project environment:

```ini
# Flask Core Configuration
SECRET_KEY=generate-a-secure-random-string-here
FLASK_DEBUG=1
APP_BASE_URL=http://127.0.0.1:5000

# Campus Branding
COLLEGE_NAME=RGUKT Ongole
COLLEGE_DOMAIN=@rguktong.ac.in

# Database Configuration:
# - To use local SQLite: Leave DATABASE_URL blank!
# - To use Cloud PostgreSQL: Provide your Supabase connection string.
DATABASE_URL=
DB_SSLMODE=require

# Administrator Credentials (Used for /admin_login)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me

# SMTP Email Configuration (Required for Password Reset OTPs)
# Configure this according to the project environment.
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM=
SMTP_USE_TLS=1

# Supabase Cloud Storage (For complaint image attachments)
# Configure this according to the project environment.
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=complaint-attachments

# OTP Expiry & Attempts
OTP_EXPIRY_MINUTES=10
OTP_MAX_ATTEMPTS=5
```

> [!NOTE]
> **Zero-Config Local Fallback:** If `DATABASE_URL` is left empty, the application automatically uses local SQLite (`database.db`). If `SUPABASE_URL` is empty, image uploads fall back safely to `static/uploads/`.

---

## 4. Initialize the Database

Run the database schema setup script to create all required tables (`students`, `complaints`, `complaint_history`, `notifications`, `password_reset_otps`):

```bash
python3 database/create_db.py
```

Expected output:
```text
Database initialized: SQLite database.db
# OR
Database initialized: PostgreSQL cloud
```

---

## 5. Launch the Application

Start the Flask development server:

```bash
python3 app.py
```

Expected output:
```text
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

Open your browser and navigate to:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 6. Verifying Key Features Locally

1. **Home Page:** Access `/`
2. **Student Registration:** Access `/register`
   - Test Student IDs: `O210894`, `N210894`, `R210894`, `S210894`
   - College Email: must match `<id>@rguktong.ac.in`
3. **Student Login:** Access `/login`
4. **Student Dashboard:** Access `/dashboard`
5. **Add Complaint & AI Analysis:** Access `/add_complaint`
   - Real-time AI prediction endpoint: `/api/ai_analyze`
6. **Admin Login:** Access `/admin_login`
   - Username: `admin` (or from your `.env`)
   - Password: `change-me` (or from your `.env`)
7. **Admin Dashboard & Analytics:** Access `/admin_dashboard` and `/analytics`
8. **Reports Export:** Test `/export_pdf` and `/export_excel`
