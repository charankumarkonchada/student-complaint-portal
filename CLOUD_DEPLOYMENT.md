# Cloud / Production Setup

This version uses **Supabase PostgreSQL** for all application records and **Supabase Storage** for complaint attachments. Supabase's dashboard lets you inspect database tables and storage files. Supabase provides Postgres, Storage, Auth, and other managed services. See the official docs: https://supabase.com/docs/guides/database/overview and https://supabase.com/docs/guides/storage.

## 1. Create the cloud database
Create a Supabase project and copy the PostgreSQL connection string into `DATABASE_URL`. For a deployed app, use the Supabase pooler connection string.

## 2. Create file storage
Create a bucket named `complaint-attachments`. The application uploads complaint images/PDFs to it. The included implementation stores the returned object URL in the `complaints.image` column.

For a strict production deployment, keep the bucket private and replace public URLs with signed URLs before launch.

## 3. Configure environment variables
Copy `.env.example` to `.env` and fill in:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- Gmail `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM`
- `SECRET_KEY`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`

**Never commit `.env` or expose the Supabase service-role key in frontend code.**

## 4. Initialize tables
```bash
pip install -r requirements.txt
python database/create_db.py
```

## 5. Run locally
```bash
python app.py
```

## 6. Production server
```bash
gunicorn --workers 3 --bind 0.0.0.0:$PORT app:app
```

Deploy the folder to a service such as Render, Railway, Fly.io, AWS, Azure, or another Python host that provides environment variables and HTTPS.

## 7. Forgot password flow
```text
Forgot Password
      ↓
Registered Email
      ↓
Generate random 6-digit OTP
      ↓
Store SHA-256 OTP hash in PostgreSQL
      ↓
Send OTP through Gmail SMTP
      ↓
User enters OTP
      ↓
Check expiry + attempt limit + hash
      ↓
OTP verified
      ↓
Create new password
      ↓
Hash password with Werkzeug
      ↓
Delete OTP
      ↓
Login
```

OTP defaults:
- 6 digits
- 10-minute expiry
- 5 maximum attempts
- one-time use

## 8. Real-world hardening before public launch
Add HTTPS, CSRF protection on all POST forms, stronger rate limiting (Redis-backed), structured logging, monitoring/error tracking, database backups, private storage with signed URLs, email delivery provider/domain authentication, and a separate production admin account.
