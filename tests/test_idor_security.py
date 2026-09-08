"""Regression tests for user-to-user IDOR boundaries."""
from app import app, db, User, Order
import commerce_extensions_v2  # noqa: F401 - registers account/order routes


def _login(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["kharidino_splash"] = "1"


def test_order_detail_api_rejects_other_users_order():
    original_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    # The application already owns the SQLAlchemy object; recreate tables on the
    # isolated in-memory connection for this regression test.
    db.engine.dispose()
    db.session.remove()
    db.drop_all()
    db.create_all()
    try:
        owner = User(name="Owner", email="owner@example.test", password="x")
        other = User(name="Other", email="other@example.test", password="x")
        db.session.add_all([owner, other])
        db.session.flush()
        order = Order(
            user_id=owner.id,
            total=1000,
            status="در انتظار بررسی",
            customer_name="Owner",
            phone="09120000000",
            address="Test address",
        )
        db.session.add(order)
        db.session.commit()

        client = app.test_client()
        _login(client, other.id)
        response = client.get(f"/api/orders/{order.id}")
        assert response.status_code == 404

        _login(client, owner.id)
        response = client.get(f"/api/orders/{order.id}")
        assert response.status_code == 200
        assert response.get_json()["id"] == order.id
    finally:
        db.session.remove()
        app.config["SQLALCHEMY_DATABASE_URI"] = original_uri
