from flask import Flask

from app import Category, Offer, Product, Store, db
from mobile_app.api.mobile_api import register_mobile_api


def make_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="mobile-api-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        register_mobile_api(app, db, Product, Category, Store, Offer)
    return app


def seed(app):
    with app.app_context():
        category = Category(name="Phones", active=True)
        active_store = Store(name="Active Store", active=True)
        inactive_store = Store(name="Inactive Store", active=False)
        db.session.add_all([category, active_store, inactive_store])
        db.session.flush()
        first = Product(name="Phone A", price=1000, category_id=category.id, active=True)
        second = Product(name="Phone B", price=2000, category_id=category.id, active=True)
        hidden = Product(name="Hidden", price=1, category_id=category.id, active=False)
        db.session.add_all([first, second, hidden])
        db.session.flush()
        db.session.add_all([
            Offer(product_id=first.id, store_id=active_store.id, price=700, in_stock=True),
            Offer(product_id=first.id, store_id=active_store.id, price=600, in_stock=False),
            Offer(product_id=first.id, store_id=inactive_store.id, price=100, in_stock=True),
            Offer(product_id=second.id, store_id=active_store.id, price=1500, in_stock=True),
        ])
        db.session.commit()
        return first.id, second.id, hidden.id


def test_mobile_compare_matches_web_offer_visibility_and_sorting():
    app = make_app()
    first_id, second_id, _ = seed(app)

    response = app.test_client().get(f"/api/mobile/compare?ids={first_id},{second_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 2
    first = data["items"][0]
    assert first["lowest_offer_price"] == 700
    assert first["highest_offer_price"] == 700
    assert first["offer_count"] == 1
    assert first["offers"][0]["store"] == "Active Store"


def test_mobile_compare_rejects_invalid_and_inactive_products():
    app = make_app()
    first_id, _, hidden_id = seed(app)
    client = app.test_client()

    assert client.get(f"/api/mobile/compare?ids={first_id}").status_code == 400
    assert client.get(f"/api/mobile/compare?ids={first_id},{first_id}").status_code == 400
    assert client.get(f"/api/mobile/compare?ids={first_id},{hidden_id}").status_code == 404


def test_mobile_product_detail_excludes_unavailable_and_inactive_store_offers():
    app = make_app()
    first_id, _, _ = seed(app)

    response = app.test_client().get(f"/api/mobile/products/{first_id}")

    assert response.status_code == 200
    offers = response.get_json()["offers"]
    assert len(offers) == 1
    assert offers[0]["price"] == 700
