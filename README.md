# Hostel Complaint Portal — Advanced / Real-World Version

A production-oriented hostel complaint management platform built with Flask, cloud PostgreSQL, cloud file storage, secure authentication, email OTP recovery, and ML-based complaint intelligence.

## Main stack
- **Backend:** Python + Flask + Gunicorn
- **Database:** PostgreSQL on Supabase
- **Cloud file storage:** Supabase Storage
- **Email:** Gmail SMTP + Google App Password
- **Frontend:** HTML/CSS/JavaScript + Jinja2
- **ML:** TF-IDF, Logistic Regression, Ridge Regression, cosine similarity
- **Reports:** ReportLab + OpenPyXL

## Authentication
- Student registration
- Student login/logout
- Secure password hashing
- Change password
- Forgot password by **6-digit OTP**
- OTP hash stored in cloud PostgreSQL
- OTP expiry
- Maximum verification attempts
- One-time OTP invalidation
- Generic response for unknown emails
- Admin login

## Cloud architecture
```text
Browser
   ↓ HTTPS
Flask + Gunicorn
   ├── PostgreSQL (Supabase) → users, complaints, history, notifications, OTPs
   ├── Supabase Storage       → complaint images / PDFs
   ├── Gmail SMTP             → password reset OTP
   └── ML Engine              → category / priority / resolution / duplicate prediction
```

## What you can see in Supabase
Database tables include:
- `students`
- `complaints`
- `complaint_history`
- `notifications`
- `password_reset_otps`
- `admin`

Attachments are visible under the `complaint-attachments` Storage bucket.

## Local development
```bash
python -m venv .venv
pip install -r requirements.txt
copy .env.example .env     # Windows
# cp .env.example .env     # Linux/macOS
python database/create_db.py
python app.py
```

## Important
The ZIP contains a template `.env.example`, not real credentials. Put your own secrets in `.env`. Never commit secrets to GitHub.
