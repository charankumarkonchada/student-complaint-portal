"""
Gunicorn production configuration for IntelliHostel.
Optimized for multi-core deployment, concurrency, and reliability.
"""
import multiprocessing
import os

# Server socket
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:" + os.environ.get("PORT", "5000"))
backlog = 2048

# Worker processes: 2 * CPUs + 1 (capped reasonably for standard servers)
cpu_count = multiprocessing.cpu_count()
workers = int(os.environ.get("WEB_CONCURRENCY", min(cpu_count * 2 + 1, 4)))
worker_class = "sync"
worker_connections = 1000
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# Process naming
proc_name = "intellihostel_app"

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.environ.get("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" (%(L)ss)'

# Preload application code
preload_app = False

# Maximum requests a worker will process before restarting (avoids memory leaks)
max_requests = 1000
max_requests_jitter = 50
