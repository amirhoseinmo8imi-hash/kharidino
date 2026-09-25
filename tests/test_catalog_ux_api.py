from flask import Flask

from app import Category, Offer, Product, Store, db
from catalog_ux_api import apply_catalog_ux_api


def make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "catalog-api-test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        apply_catalog_ux_api(app, db, Product, Category, Offer, Store)
    return app


def seed_catalog(app):
    with app.app_context():
        category = Category(name="Test", active=True)
        store = Store(name="Active Store", active=True)
        inactive_store = Store(name="Inactive Store", active=False)
        db.session.add_all([category, store, inactive_store])
        db.session.flush()

        cheap = Product(name="Cheap Phone", description="Budget phone", price=900, category_id=category.id, active=True)
        expensive = Product(name="Expensive Phone", description="Premium phone", price=9000, category_id=category.id, active=True)
        hidden = Product(name="Hidden Phone", description="Not public", price=100, category_id=category.id, active=False)
        db.session.add_all([cheap, expensive, hidden])
        db.session.flush()
        db.session.add_all([
            Offer(product_id=cheap.id, store_id=store.id, price=500, in_stock=True),
            Offer(product_id=expensive.id, store_id=store.id, price=8000, in_stock=True),
            Offer(product_id=expensive.id, store_id=inactive_store.id, price=100, in_stock=True),
        ])
        db.session.commit()
        return cheap.id, expensive.id, hidden.id


def test_catalog_search_returns_only_active_products_and_lowest_active_offer_price():
    app = make_app()
    cheap_id, expensive_id, hidden_id = seed_catalog(app)
    response = app.test_client().get("/api/catalog/search?sort=price_low")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 2
    assert [item["id"] for item in data["items"]] == [cheap_id, expensive_id]
    assert data["items"][0]["price"] == 500
    assert data["items"][0]["in_stock"] is True
    assert hidden_id not in {item["id"] for item in data["items"]}


def test_catalog_price_filter_uses_effective_offer_price():
    app = make_app()
    cheap_id, expensive_id, _ = seed_catalog(app)
    response = app.test_client().get("/api/catalog/search?min_price=600&max_price=8500")
    assert response.status_code == 200
    assert [item["id"] for item in response.get_json()["items"]] == [expensive_id]
    assert cheap_id not in {item["id"] for item in response.get_json()["items"]}


def test_catalog_invalid_filter_returns_bad_request():
    app = make_app()
    response = app.test_client().get("/api/catalog/search?page=nope")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_filter"


def test_catalog_invalid_price_range_returns_bad_request():
    app = make_app()
    response = app.test_client().get("/api/catalog/search?min_price=900&max_price=100")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_price_range"


def test_catalog_pagination_caps_page_size():
    app = make_app()
    seed_catalog(app)
    response = app.test_client().get("/api/catalog/search?per_page=999&page=1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["per_page"] == 40
    assert data["pages"] == 1
