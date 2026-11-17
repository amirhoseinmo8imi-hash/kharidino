from flask import Flask

from app import Category, Offer, Product, Store, db
from catalog_ux_api import apply_catalog_ux_api, normalize_search_text


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



def test_catalog_compare_returns_active_store_offers_sorted_by_price():
    app = make_app()
    cheap_id, expensive_id, _ = seed_catalog(app)

    response = app.test_client().get(f"/api/catalog/compare?ids={expensive_id},{cheap_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 2
    assert [item["id"] for item in data["items"]] == [expensive_id, cheap_id]
    expensive = data["items"][0]
    assert expensive["lowest_offer_price"] == 8000
    assert expensive["highest_offer_price"] == 8000
    assert expensive["offer_count"] == 1
    assert expensive["offers"][0]["store"] == "Active Store"


def test_catalog_compare_requires_two_to_four_distinct_ids():
    app = make_app()
    client = app.test_client()

    assert client.get("/api/catalog/compare?ids=1").status_code == 400
    assert client.get("/api/catalog/compare?ids=1,1").status_code == 400
    assert client.get("/api/catalog/compare?ids=1,2,3,4,5").status_code == 400
    assert client.get("/api/catalog/compare?ids=one,two").status_code == 400


def test_catalog_compare_does_not_expose_inactive_products():
    app = make_app()
    cheap_id, _, hidden_id = seed_catalog(app)

    response = app.test_client().get(f"/api/catalog/compare?ids={cheap_id},{hidden_id}")

    assert response.status_code == 404
    assert response.get_json()["error"] == "products_not_found"



def test_persian_search_normalization_handles_arabic_keyboard_variants():
    assert normalize_search_text("  كالاى   ويژه  ") == "کالای ویژه"
    assert normalize_search_text("هَزینه") == "هزینه"


def test_catalog_search_matches_persian_arabic_keyboard_variants():
    app = make_app()
    with app.app_context():
        product = Product(name="کالای ویژه", description="توضیحات فارسی", price=1200, active=True)
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = app.test_client().get("/api/catalog/search?q=كالاى")
    assert response.status_code == 200
    data = response.get_json()
    assert data["query"] == "کالای"
    assert [item["id"] for item in data["items"]] == [product_id]


def test_catalog_stock_filter_only_uses_active_store_offers():
    app = make_app()
    cheap_id, expensive_id, _ = seed_catalog(app)
    with app.app_context():
        unavailable = Product(name="Unavailable Product", description="", price=300, active=True)
        db.session.add(unavailable)
        db.session.commit()
        unavailable_id = unavailable.id

    client = app.test_client()
    available = client.get("/api/catalog/search?stock=available").get_json()
    unavailable_data = client.get("/api/catalog/search?stock=unavailable").get_json()

    assert {item["id"] for item in available["items"]} == {cheap_id, expensive_id}
    assert {item["id"] for item in unavailable_data["items"]} == {unavailable_id}
    assert client.get("/api/catalog/search?stock=unknown").status_code == 400
