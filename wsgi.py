"""Production WSGI entrypoint for Kharidino.

The application has one canonical initialization path: run_kharidino.py.
WSGI reuses it so production and local execution register the same security,
commerce, payment and marketplace extensions.
"""
import os

# WSGI must never seed demo/catalog data on import.
os.environ.setdefault("KHARIDINO_SKIP_SEED", "1")

from run_kharidino import app  # noqa: E402,F401
