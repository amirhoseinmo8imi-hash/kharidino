Security hardening is applied by `security_hardening.py` and loaded by `run_kharidino.py` and `wsgi.py`.

Production entrypoint: `gunicorn wsgi:app`.

Set `SECRET_KEY` and `KHARIDINO_PRODUCTION=1` in production. Never commit secrets.
