# Multi-stage / Production Dockerfile for IntelliHostel Student Complaint Portal
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files to disk and disable output buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

# Install system dependencies needed for compiling extensions and PostgreSQL driver
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create uploads directory and non-privileged user for security
RUN mkdir -p /app/static/uploads && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

# Healthcheck to ensure container is responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Production command using Gunicorn WSGI
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
