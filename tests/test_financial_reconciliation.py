import os
from concurrent.futures import ThreadPoolExecutor


def _boot():
    os.environ["PAYMENT_TEST_MODE"] = "1"
    import run_kharidino  # noqa: F401
    from app import app, db, Order, Store, User
    from merchant_marketplace_v2 import SellerLedger, SellerOrder
    from accounting import SellerSettlement, SellerSettlementAllocation
    return app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation


def test_reconciliation_passes_for_balanced_paid_refunded_flow():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation = _boot()
    with app.app_context():
        PaymentTransaction = app.extensions["kharidino_payment_transaction"]
        from financial_reconciliation import reconcile_all
        user = User(name="Recon Pass", email="recon-pass@example.invalid", password="x", role="admin")
        store = Store(name="Recon Pass Store", active=True)
        db.session.add_all([user, store]); db.session.flush()
        order = Order(user_id=user.id, total=100_000, status="تأیید شد", customer_name="Recon", phone="09121111111", address="Test")
        db.session.add(order); db.session.flush()
        sub = SellerOrder(order_id=order.id, store_id=store.id, status="new", subtotal=100_000, shipping_fee=0, platform_fee=5_000, seller_total=95_000)
        db.session.add(sub); db.session.flush()
        ledger = SellerLedger(seller_order_id=sub.id, store_id=store.id, gross=100_000, shipping=0, platform_fee=5_000, net=95_000, status="available")
        db.session.add(ledger)
        tx = PaymentTransaction(order_id=order.id, user_id=user.id, amount=100_000, status="paid", gateway="test", authority=f"RECON-{order.id}", idempotency_key=f"RECON-IDEMP-{order.id}")
        db.session.add(tx); db.session.commit()
        failures = reconcile_all()
        assert failures == []
        # Deliberately corrupt one accounting fact and prove reconciliation catches it.
        ledger.net = 94_999; db.session.commit()
        failures = reconcile_all()
        assert any(item["type"] == "ledger" and item["id"] == ledger.id for item in failures)
        db.session.rollback()
        ledger.net = 95_000; db.session.delete(tx); db.session.delete(ledger); db.session.delete(sub); db.session.delete(order); db.session.delete(store); db.session.delete(user); db.session.commit()


def test_two_database_connections_cannot_allocate_same_ledger_twice():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation = _boot()
    with app.app_context():
        user = User(name="Race Guard", email="race-guard@example.invalid", password="x", role="admin")
        store = Store(name="Race Guard Store", active=True)
        db.session.add_all([user, store]); db.session.flush()
        order = Order(user_id=user.id, total=100_000, status="تأیید شد", customer_name="Race", phone="09122222222", address="Test")
        db.session.add(order); db.session.flush()
        sub = SellerOrder(order_id=order.id, store_id=store.id, status="new", subtotal=100_000, shipping_fee=0, platform_fee=5_000, seller_total=95_000)
        db.session.add(sub); db.session.flush()
        ledger = SellerLedger(seller_order_id=sub.id, store_id=store.id, gross=100_000, shipping=0, platform_fee=5_000, net=95_000, status="available")
        first = SellerSettlement(store_id=store.id, amount=95_000, status="requested", requested_by=user.id)
        second = SellerSettlement(store_id=store.id, amount=95_000, status="requested", requested_by=user.id)
        db.session.add_all([ledger, first, second]); db.session.commit()
        ledger_id, first_id, second_id = ledger.id, first.id, second.id
        engine = db.engine

    def attempt(settlement_id):
        conn = engine.connect()
        trans = conn.begin()
        try:
            conn.exec_driver_sql(
                "INSERT INTO kharidino_seller_settlement_allocation (settlement_id, ledger_id, amount) VALUES (?, ?, ?)",
                (settlement_id, ledger_id, 95_000),
            )
            trans.commit()
            return True
        except Exception:
            trans.rollback()
            return False
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [first_id, second_id]))
    with app.app_context():
        assert sorted(results) == [False, True]
        assert SellerSettlementAllocation.query.filter_by(ledger_id=ledger_id).count() == 1
        db.session.query(SellerSettlement).filter(SellerSettlement.id.in_([first_id, second_id])).delete(synchronize_session=False)
        db.session.delete(db.session.get(SellerLedger, ledger_id)); db.session.delete(db.session.get(SellerOrder, sub.id)); db.session.delete(db.session.get(Order, order.id)); db.session.delete(store); db.session.delete(user); db.session.commit()
