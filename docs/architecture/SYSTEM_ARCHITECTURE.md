# IntelliHostel System Architecture

## Architecture Overview

IntelliHostel is a modular, production-ready web application built with Flask, Jinja2, PostgreSQL (via Supabase), Supabase Storage, and Scikit-Learn NLP.

```mermaid
graph TD
    Client["Student & Admin Browsers"]
    Vercel["PaaS / Vercel Serverless / Gunicorn"]
    AppFactory["Flask Factory (backend/app.py)"]
    Blueprints["Modular Blueprints (backend/routes/*)"]
    Services["Business Services (backend/services/*)"]
    MLEngine["ML Engine (ml/ml_engine.py)"]
    Database["Supabase PostgreSQL (or SQLite Dev)"]
    Storage["Supabase Object Storage"]
    SMTP["Gmail SMTP (Port 587)"]

    Client -->|HTTPS Requests| Vercel
    Vercel -->|WSGI / HTTP Handler| AppFactory
    AppFactory --> Blueprints
    Blueprints --> Services
    Services --> Database
    Services --> Storage
    Services --> SMTP
    Blueprints --> MLEngine
```

## Layers
1. **Frontend (`frontend/`)**: Modular Jinja2 templates (`base.html`, `public/`, `student/`, `admin/`, `errors/`) and static assets (`css/`, `js/`, `images/`).
2. **Backend Entrypoint (`app.py`, `wsgi.py`)**: Thin WSGI layer delegating to `backend.app.create_app()`.
3. **Application Core (`backend/`)**:
   - `backend/config/`: Environment configuration loaded from `.env`.
   - `backend/database/`: PostgreSQL / SQLite connection pooling and schema initialization.
   - `backend/services/`: Authentication, CSRF protection, email delivery, notifications, cloud storage, and common issue clustering.
   - `backend/routes/`: Modular team blueprints for administrative and student operations.
4. **Machine Learning (`ml/`)**: Logistic regression and Ridge regression models trained from `data/training_data.csv`.
5. **Data Layer (`data/`)**: Canonical training datasets.
