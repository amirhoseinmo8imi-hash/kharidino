"""Conservative production Gunicorn defaults for Kharidino."""
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = max(1, int(os.environ.get("WEB_CONCURRENCY", "2")))
threads = max(1, int(os.environ.get("GUNICORN_THREADS", "2")))
timeout = max(30, int(os.environ.get("GUNICORN_TIMEOUT", "60")))
keepalive = 5
worker_tmp_dir = "/dev/shm"
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
preload_app = False
