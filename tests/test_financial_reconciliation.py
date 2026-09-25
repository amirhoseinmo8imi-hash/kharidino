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
        from financial_reconciliation import reconcile_payment, reconcile_ledger
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
        # Audit this transaction specifically so unrelated immutable journals from
        # earlier tests cannot make a focused reconciliation test order-dependent.
        assert reconcile_payment(tx) == []
        ledger.net = 94_999; db.session.commit()
        assert any("net mismatch" in error for error in reconcile_ledger(ledger))
        ledger.net = 95_000
        # Keep the financial transaction and its related rows in this shared CI
        # database. Deleting the order here makes SQLAlchemy try to NULL the
        # PaymentTransaction.order_id FK, which is intentionally NOT NULL, and
        # can also recycle SQLite integer ids for later financial facts. The test
        # data is uniquely keyed and harmless to subsequent reconciliation checks.
        db.session.commit()


def test_two_database_connections_cannot_allocate_same_ledger_twice():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation = _boot()
    with app.app_context():
        user = User(name="Race Guard", email="race-guard@example.invalid", password="x", role="admin")
        store = Store(name="Race Guard Store", active=True)
        db.session.add_all([user, store]); db.session.flush()
        order = Order(user_id=user.id, total=100_000, status="تأیید شد", customer_name="Race", phone="09122222222", address="Test")
        db.session.add(order); db.session.flush()
        order_id = order.id
        sub = SellerOrder(order_id=order_id, store_id=store.id, status="new", subtotal=100_000, shipping_fee=0, platform_fee=5_000, seller_total=95_000)
        db.session.add(sub); db.session.flush()
        sub_id = sub.id
        ledger = SellerLedger(seller_order_id=sub_id, store_id=store.id, gross=100_000, shipping=0, platform_fee=5_000, net=95_000, status="available")
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
        db.session.delete(db.session.get(SellerLedger, ledger_id)); db.session.delete(db.session.get(SellerOrder, sub_id)); db.session.delete(db.session.get(Order, order_id)); db.session.delete(store); db.session.delete(user); db.session.commit()
