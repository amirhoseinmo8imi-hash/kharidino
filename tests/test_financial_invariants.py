import os

import pytest


def _boot():
    os.environ["PAYMENT_TEST_MODE"] = "1"
    import run_kharidino  # noqa: F401
    from app import app, db, Order, Store, User
    from merchant_marketplace_v2 import SellerLedger, SellerOrder
    from accounting import SellerSettlement, SellerSettlementAllocation
    PaymentTransaction = app.extensions["kharidino_payment_transaction"]
    return app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation, PaymentTransaction


def _make_flow(app, db, Order, SellerOrder, SellerLedger, user, store, *, ledger_status="available"):
    order = Order(user_id=user.id, total=100_000, status="تأیید شد", customer_name="Adversarial", phone="09121111111", address="Test")
    db.session.add(order); db.session.flush()
    seller_order = SellerOrder(order_id=order.id, store_id=store.id, status="new", subtotal=100_000, shipping_fee=0, platform_fee=5_000, seller_total=95_000)
    db.session.add(seller_order); db.session.flush()
    ledger = SellerLedger(seller_order_id=seller_order.id, store_id=store.id, gross=100_000, shipping=0, platform_fee=5_000, net=95_000, status=ledger_status)
    db.session.add(ledger); db.session.flush()
    PaymentTransaction = app.extensions["kharidino_payment_transaction"]
    tx = PaymentTransaction(order_id=order.id, user_id=user.id, amount=100_000, status="paid", gateway="test", authority=f"AUTH-{order.id}", idempotency_key=f"IDEMP-{order.id}")
    db.session.add(tx); db.session.commit()
    return order, seller_order, ledger, tx


def _refund(app, user, tx):
    from flask import session
    with app.test_request_context(f"/payment/refund/{tx.public_id}", method="POST"):
        session["user_id"] = user.id
        response = app.view_functions["payment_refund"](transaction_id=tx.public_id)
        assert response.status_code in {301, 302, 303, 307, 308}


def test_refund_before_settlement_has_no_clawback_and_is_idempotent():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation, PaymentTransaction = _boot()
    RefundRecord = app.extensions["kharidino_refund_record"]
    SellerClawback = app.extensions["kharidino_seller_clawback"]
    with app.app_context():
        user = User(name="Refund Before", email="refund-before@example.invalid", password="x", role="admin")
        store = Store(name="Refund Before Store", active=True); db.session.add_all([user, store]); db.session.flush()
        order, seller_order, ledger, tx = _make_flow(app, db, Order, SellerOrder, SellerLedger, user, store, ledger_status="pending")
        _refund(app, user, tx); db.session.expire_all()
        assert db.session.get(PaymentTransaction, tx.id).status == "refunded"
        assert db.session.get(Order, order.id).status == "لغو شد"
        assert db.session.get(SellerLedger, ledger.id).status == "cancelled"
        refund = RefundRecord.query.filter_by(payment_transaction_id=tx.id).one()
        assert SellerClawback.query.filter_by(refund_id=refund.id).count() == 0
        _refund(app, user, tx)
        assert RefundRecord.query.filter_by(payment_transaction_id=tx.id).count() == 1
        assert SellerClawback.query.filter_by(refund_id=refund.id).count() == 0
        db.session.delete(refund); db.session.delete(db.session.get(PaymentTransaction, tx.id)); db.session.delete(db.session.get(SellerLedger, ledger.id)); db.session.delete(db.session.get(SellerOrder, seller_order.id)); db.session.delete(db.session.get(Order, order.id)); db.session.delete(store); db.session.delete(user); db.session.commit()


def test_refund_during_requested_settlement_cancels_reservation():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation, PaymentTransaction = _boot()
    RefundRecord = app.extensions["kharidino_refund_record"]
    with app.app_context():
        user = User(name="Requested Refund", email="requested-refund@example.invalid", password="x", role="admin")
        store = Store(name="Requested Refund Store", active=True); db.session.add_all([user, store]); db.session.flush()
        order, seller_order, ledger, tx = _make_flow(app, db, Order, SellerOrder, SellerLedger, user, store)
        settlement = SellerSettlement(store_id=store.id, amount=95_000, status="requested", requested_by=user.id)
        db.session.add(settlement); db.session.flush(); db.session.add(SellerSettlementAllocation(settlement_id=settlement.id, ledger_id=ledger.id, amount=95_000)); db.session.commit()
        _refund(app, user, tx); db.session.expire_all()
        settlement = db.session.get(SellerSettlement, settlement.id)
        assert settlement.status == "cancelled"
        assert SellerSettlementAllocation.query.filter_by(settlement_id=settlement.id).count() == 0
        assert RefundRecord.query.filter_by(payment_transaction_id=tx.id, status="succeeded").count() == 1
        refund = RefundRecord.query.filter_by(payment_transaction_id=tx.id).one()
        db.session.delete(refund); db.session.delete(db.session.get(PaymentTransaction, tx.id)); db.session.delete(settlement); db.session.delete(db.session.get(SellerLedger, ledger.id)); db.session.delete(db.session.get(SellerOrder, seller_order.id)); db.session.delete(db.session.get(Order, order.id)); db.session.delete(store); db.session.delete(user); db.session.commit()


def test_partial_then_full_clawback_reconciles_exactly_once():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation, PaymentTransaction = _boot()
    SellerClawback = app.extensions["kharidino_seller_clawback"]
    Resolution = app.extensions["kharidino_seller_clawback_resolution"]
    with app.app_context():
        user = User(name="Clawback Test", email="clawback@example.invalid", password="x", role="admin")
        store = Store(name="Clawback Store", active=True); db.session.add_all([user, store]); db.session.flush()
        order, seller_order, ledger, tx = _make_flow(app, db, Order, SellerOrder, SellerLedger, user, store, ledger_status="paid")
        settlement = SellerSettlement(store_id=store.id, amount=95_000, status="paid", requested_by=user.id, processed_by=user.id)
        db.session.add(settlement); db.session.flush(); allocation = SellerSettlementAllocation(settlement_id=settlement.id, ledger_id=ledger.id, amount=95_000); db.session.add(allocation); db.session.commit()
        _refund(app, user, tx)
        refund = app.extensions["kharidino_refund_record"].query.filter_by(payment_transaction_id=tx.id).one()
        clawback = SellerClawback.query.filter_by(refund_id=refund.id, seller_ledger_id=ledger.id).one()
        db.session.add(Resolution(clawback_id=clawback.id, amount=40_000, reference=f"PARTIAL-{clawback.id}", processed_by=user.id)); db.session.commit(); db.session.expire_all()
        assert db.session.get(SellerClawback, clawback.id).status == "partial"
        db.session.add(Resolution(clawback_id=clawback.id, amount=55_000, reference=f"FULL-{clawback.id}", processed_by=user.id)); db.session.commit(); db.session.expire_all()
        assert db.session.get(SellerClawback, clawback.id).status == "settled"
        assert db.session.query(db.func.sum(Resolution.amount)).filter_by(clawback_id=clawback.id).scalar() == 95_000
        with pytest.raises(ValueError):
            db.session.add(Resolution(clawback_id=clawback.id, amount=1, reference=f"OVER-{clawback.id}", processed_by=user.id)); db.session.flush()
        db.session.rollback()
        assert Resolution.query.filter_by(clawback_id=clawback.id).count() == 2
        db.session.delete(clawback); db.session.delete(refund); db.session.delete(db.session.get(PaymentTransaction, tx.id)); db.session.delete(settlement); db.session.delete(db.session.get(SellerLedger, ledger.id)); db.session.delete(db.session.get(SellerOrder, seller_order.id)); db.session.delete(db.session.get(Order, order.id)); db.session.delete(store); db.session.delete(user); db.session.commit()


def test_database_guard_rejects_cross_settlement_double_allocation():
    app, db, Order, Store, User, SellerLedger, SellerOrder, SellerSettlement, SellerSettlementAllocation, PaymentTransaction = _boot()
    with app.app_context():
        user = User(name="Allocation Guard", email="allocation-guard@example.invalid", password="x", role="admin")
        store = Store(name="Allocation Guard Store", active=True); db.session.add_all([user, store]); db.session.flush()
        order, seller_order, ledger, tx = _make_flow(app, db, Order, SellerOrder, SellerLedger, user, store)
        first = SellerSettlement(store_id=store.id, amount=60_000, status="requested", requested_by=user.id)
        second = SellerSettlement(store_id=store.id, amount=60_000, status="requested", requested_by=user.id)
        db.session.add_all([first, second]); db.session.flush(); db.session.add(SellerSettlementAllocation(settlement_id=first.id, ledger_id=ledger.id, amount=60_000)); db.session.commit()
        db.session.add(SellerSettlementAllocation(settlement_id=second.id, ledger_id=ledger.id, amount=60_000))
        with pytest.raises(Exception): db.session.commit()
        db.session.rollback()
        assert SellerSettlementAllocation.query.filter_by(ledger_id=ledger.id).count() == 1
        db.session.delete(db.session.get(SellerSettlement, first.id)); db.session.delete(db.session.get(SellerSettlement, second.id)); db.session.delete(db.session.get(PaymentTransaction, tx.id)); db.session.delete(db.session.get(SellerLedger, ledger.id)); db.session.delete(db.session.get(SellerOrder, seller_order.id)); db.session.delete(db.session.get(Order, order.id)); db.session.delete(store); db.session.delete(user); db.session.commit()
