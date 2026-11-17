from flask import Flask

from app import Offer, Product, Store, db
from platform_api import register_platform_api


def make_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="platform-api-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        register_platform_api(app, db, Product, Offer, Store)
    return app


def test_versioned_market_search_normalizes_persian_and_filters_stock():
    app = make_app()
    with app.app_context():
        active_store = Store(name="Active", active=True)
        inactive_store = Store(name="Inactive", active=False)
        db.session.add_all([active_store, inactive_store])
        db.session.flush()
        available = Product(name="کالای ویژه", description="محصول آزمایشی", price=2000, active=True)
        unavailable = Product(name="کالای دیگر", description="", price=3000, active=True)
        db.session.add_all([available, unavailable])
        db.session.flush()
        db.session.add_all([
            Offer(product_id=available.id, store_id=active_store.id, price=1500, in_stock=True),
            Offer(product_id=unavailable.id, store_id=inactive_store.id, price=100, in_stock=True),
        ])
        available_id = available.id
        db.session.commit()

    client = app.test_client()
    response = client.get("/api/v1/market/products?q=كالاى&stock=available")
    assert response.status_code == 200
    data = response.get_json()
    assert data["query"] == "کالای"
    assert data["total"] == 1
    assert data["items"][0]["id"] == available_id
    assert data["items"][0]["price"] == 1500
    assert data["items"][0]["store_count"] == 1
    assert data["items"][0]["in_stock"] is True


def test_versioned_market_search_supports_sorting_and_validates_filters():
    app = make_app()
    with app.app_context():
        db.session.add_all([
            Product(name="Z Phone", description="", price=900, active=True),
            Product(name="A Phone", description="", price=400, active=True),
        ])
        db.session.commit()

    client = app.test_client()
    response = client.get("/api/v1/market/products?sort=name&per_page=1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["items"][0]["name"] == "A Phone"
    assert data["pages"] == 2
    assert data["per_page"] == 1
    assert client.get("/api/v1/market/products?stock=broken").status_code == 400
    assert client.get("/api/v1/market/products?page=0").status_code == 400
    assert client.get("/api/v1/market/products?sort=broken").status_code == 400
