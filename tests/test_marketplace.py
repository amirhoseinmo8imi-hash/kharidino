import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SECRET_KEY", "test-secret")

from app import app, db, Product, Category, Store, Offer, User, login_required, admin_required
from marketplace import register

register(app, db, Product, Category, Store, Offer, User, login_required, admin_required)


def test_marketplace_models_registered():
    models = app.extensions["kharidino_marketplace"]
    assert "SellerProfile" in models
    assert "SellerListing" in models
    assert "SellerWallet" in models
    assert "SellerLedgerEntry" in models
    assert "MarketplaceMessage" in models


def test_seller_dashboard_requires_login():
    client = app.test_client()
    response = client.get("/marketplace/seller")
    assert response.status_code in (302, 401, 403)


def test_public_storefront_hides_unapproved_sellers():
    client = app.test_client()
    response = client.get("/shop/not-an-approved-shop")
    assert response.status_code == 404


def test_message_requires_authentication():
    client = app.test_client()
    response = client.post("/marketplace/message", data={"recipient_id": 1, "body": "hello"})
    assert response.status_code in (302, 401, 403)
