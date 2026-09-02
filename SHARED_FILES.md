# Shared Infrastructure & Central Integration Assets

**INTEGRATION OWNER: K. Charankumar (0221168)**

This document lists all shared infrastructure, services, database files, and central templates. These files belong **exclusively** to the Integration Owner. All team members can read and use these assets in their features, but they must **NOT** modify them without explicit approval from K. Charankumar.

---

## Shared Infrastructure Registry

| File / Folder | Purpose | Owner | Can Members Modify? |
| :--- | :--- | :--- | :--- |
| `app.py` | Application factory, global Jinja context processors, 404/500 error handlers, blueprint registration. | K. Charankumar (`0221168`) | **NO** — Managed exclusively by Admin |
| `config.py` | Environment configuration, secrets loader, DB URLs, storage settings, mail parameters, and application constants. | K. Charankumar (`0221168`) | **NO** — Managed exclusively by Admin |
| `requirements.txt` | Core Python dependencies and version specifications. | K. Charankumar (`0221168`) | **NO** — Requires Admin approval to add packages |
| `routes/__init__.py` | Central blueprint registration hub and dynamic `url_for` aliasing handler. | K. Charankumar (`0221168`) | **NO** — Integration layer maintained by Admin |
| `database/db.py` | Dual-engine database connection manager (PostgreSQL Cloud pooler + local SQLite fallback). | K. Charankumar (`0221168`) | **NO** — Core database connection infrastructure |
| `database/create_db.py` | Schema initializations, table migrations (`students`, `complaints`, `history`, `otps`, `notifications`). | K. Charankumar (`0221168`) | **NO** — Database schema cannot be modified |
| `database/queries.py` | Shared SQL helper functions (`complaint_for_student`). | K. Charankumar (`0221168`) | **NO** — Reusable database queries |
| `services/auth_service.py` | Multi-campus ID format validation (`is_valid_id` for O/N/R/S), email check, OTP hashing, auth decorators. | K. Charankumar (`0221168`) | **NO** — Centralized security & validation rule |
| `services/email_service.py` | SMTP mail sender for password reset OTPs and student alerts. | K. Charankumar (`0221168`) | **NO** — Reusable email service |
| `services/storage_service.py` | Supabase Cloud Storage integration and local attachment upload fallback. | K. Charankumar (`0221168`) | **NO** — File storage infrastructure |
| `ml_engine.py` | TF-IDF + Naive Bayes AI engine for complaint classification, priority prediction, and duplicate detection. | K. Charankumar (`0221168`) | **NO** — Shared machine learning service |
| `templates/base.html` | Shared global layout, navigation header, mobile sidebar, flash alerts, and footer. | K. Charankumar (`0221168`) | **NO** — Extend using `{% extends "base.html" %}` only |
| `static/css/shared/style.css`<br>`static/css/style.css` | Global design system, CSS variables, typography, navbar, buttons, and animations. | K. Charankumar (`0221168`) | **NO** — Member features use their own CSS files |
| `static/js/shared/script.js`<br>`static/js/script.js` | Global script for toasts, navbar interactions, and scroll-to-top handler. | K. Charankumar (`0221168`) | **NO** — Member features use their own JS files |
| `static/images/` | Shared logos, campus badges, and favicon SVGs. | K. Charankumar (`0221168`) | **NO** — Shared visual branding |
| `.gitignore` | Prevents secrets (`.env`), cache (`__pycache__`), virtual environments, and local DBs from entering Git. | K. Charankumar (`0221168`) | **NO** — Managed by Admin |
| `.env.example` | Template demonstrating required environment variable names with zero real secrets. | K. Charankumar (`0221168`) | **NO** — Managed by Admin |

---

## Base Template Extension Rule

All member templates are designed to inherit from `templates/base.html`:

```jinja2
{% extends "base.html" %}

{% block title %}Feature Title - Hostel Complaint Portal{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/<member>/<feature>.css') }}">
{% endblock %}

{% block content %}
<!-- Member's HTML content goes here -->
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/<member>/<feature>.js') }}"></script>
{% endblock %}
```

Members must **never** edit `templates/base.html` or duplicate its layout logic inside their individual templates.
