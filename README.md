# IntelliHostel — Modular Student Complaint Portal

An enterprise-grade, AI-assisted Student Hostel Complaint Management System designed for RGUKT. Built with Flask, PostgreSQL (via Supabase), Supabase Object Storage, Gmail SMTP, and Scikit-Learn NLP.

---

## 📁 Production Directory Structure

```text
student-complaint-portal/
│
├── app.py                     # Top-level application entry point (Vercel & local execution)
├── wsgi.py                    # Production WSGI entry point (Gunicorn)
├── requirements.txt           # Python dependencies
├── runtime.txt                # Python runtime specification
├── Procfile                   # Process definition for deployment platforms
├── Dockerfile                 # Container image specification
├── docker-compose.yml         # Container orchestration configuration
├── gunicorn.conf.py           # Production Gunicorn worker settings
├── .gitignore                 # Git ignore rules
├── .env.example               # Environment template
├── README.md                  # Project overview
│
├── frontend/
│   ├── templates/             # Jinja2 HTML templates
│   │   ├── base.html          # Base layout template
│   │   ├── public/            # Public-facing views (index.html)
│   │   ├── student/           # Student portals (login, register, dashboard, complaints, etc.)
│   │   ├── admin/             # Admin portals (admin_login, dashboard, manage, analytics, etc.)
│   │   └── errors/            # HTTP error handlers (404.html, 500.html)
│   │
│   └── static/                # Static assets
│       ├── css/               # Modular CSS and global style.css
│       ├── js/                # Modular JavaScript and global script.js
│       ├── images/            # SVGs, icons, branding
│       └── uploads/           # Local development upload directory (.gitkeep)
│
├── backend/
│   ├── __init__.py            # Backend package root
│   ├── app.py                 # Core Flask application factory (create_app)
│   ├── config/                # Centralized configuration settings
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── database/              # Database adapters, schema bootstrap & queries
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── queries.py
│   │   └── create_db.py
│   ├── routes/                # Modular blueprint route packages
│   │   ├── __init__.py
│   │   ├── charan/            # Admin login, manage complaints, update status, common issues
│   │   ├── charankumar/       # Admin dashboard, analytics, export reports
│   │   ├── jagan/             # Public home, add complaint, complaint history, view complaint
│   │   ├── rushmitha/         # Register, edit complaint, student profile
│   │   ├── deepthi/           # Student login, password reset flow, notifications
│   │   └── vennela/           # Student dashboard, activity log
│   ├── services/              # Business & infrastructure services
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── common_issue_service.py
│   │   ├── csrf_service.py
│   │   ├── email_service.py
│   │   ├── notification_service.py
│   │   └── storage_service.py
│   └── utils/                 # Utility helpers
│       └── __init__.py
│
├── ml/
│   ├── __init__.py            # Machine Learning engine package
│   ├── ml_engine.py           # NLP classifier, Ridge regression, duplicate detection
│   └── models/                # ML model artifacts (.gitkeep)
│
├── data/
│   ├── training_data.csv      # Training dataset for AI models
│   └── README.md              # Dataset documentation
│
├── tests/
│   ├── conftest.py            # Global test fixtures & test safety guards
│   ├── test_archived_notifications.py
│   ├── test_common_issues.py
│   ├── test_e2e_workflows.py
│   ├── test_email_isolation_regression.py
│   ├── test_email_notifications.py
│   ├── test_forgot_password.py
│   ├── test_logout_confirmation.py
│   ├── test_password_visibility.py
│   └── test_theme_system.py
│
├── docs/
│   ├── diagrams/              # Architectural diagrams
│   │   ├── uml/
│   │   └── dfd/
│   ├── deployment/            # Deployment and operational guides
│   │   ├── CLOUD_DEPLOYMENT.md
│   │   ├── EMAIL_SETUP.md
│   │   └── RUN_PROJECT.md
│   ├── architecture/          # Architecture overview
│   │   └── SYSTEM_ARCHITECTURE.md
│   └── project-documentation/ # Project guides and documentation
│
└── scripts/
    ├── development/           # Development convenience scripts (run_dev.sh)
    ├── database/              # Database bootstrap scripts (init_db.py)
    └── maintenance/           # Maintenance and cleanup tasks (group_common_issues.py)
```

---

## 👥 Team Module Ownership

| Team Member | Role / Feature Ownership | Backend Routes | Templates | Static Assets |
| :--- | :--- | :--- | :--- | :--- |
| **R. Charan Kumar** | Admin Login, Manage Complaints, Update Status, Common Issues, 404 Page | `backend/routes/charan/` | `frontend/templates/admin/`, `frontend/templates/errors/` | `frontend/static/{css,js}/charan/` |
| **K. Charankumar** | Admin Dashboard, Analytics Dashboard, Reports Export, **Project Integration** | `backend/routes/charankumar/` | `frontend/templates/admin/` | `frontend/static/{css,js}/charankumar/` |
| **B. Jagan** | Home Page, Add Complaint, Complaint History, View Complaint Details | `backend/routes/jagan/` | `frontend/templates/public/`, `frontend/templates/student/` | `frontend/static/{css,js}/jagan/` |
| **M. Rushmitha** | Student Registration, Edit Complaint, Delete Complaint, Student Profile | `backend/routes/rushmitha/` | `frontend/templates/student/` | `frontend/static/{css,js}/rushmitha/` |
| **K. Deepthi** | Student Login, Password Reset (OTP), Notifications | `backend/routes/deepthi/` | `frontend/templates/student/` | `frontend/static/{css,js}/deepthi/` |
| **K. Vennela** | Student Dashboard, Activity Feed, 500 Error Page | `backend/routes/vennela/` | `frontend/templates/student/`, `frontend/templates/errors/` | `frontend/static/{css,js}/vennela/` |

---

## 🚀 Running the Project Locally

```bash
# 1. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Initialize database
python3 scripts/database/init_db.py

# 5. Launch server
python3 app.py
```
Open `http://127.0.0.1:5000` in your web browser.

---

## 🧪 Running Automated Tests

Run the complete test suite:
```bash
pytest -q
# OR
python3 -m unittest discover tests
```
