import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SECRET_KEY", "test-secret")

from app import app, db, Product, Store, Offer, User, admin_required  # noqa: E402
from kharidino_ai import register  # noqa: E402

register(app, db, Product, Store, Offer, User, admin_required)


def test_ai_dashboard_requires_login():
    client = app.test_client()
    response = client.get("/admin/kharidino-ai/")
    assert response.status_code in (302, 401, 403)


def test_app_has_ai_blueprint():
    assert "kharidino_ai.dashboard" in app.view_functions
