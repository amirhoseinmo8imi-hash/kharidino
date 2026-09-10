import os


def test_payment_refund_settlement_clawback_is_idempotent():
    os.environ["PAYMENT_TEST_MODE"] = "1"

    import run_kharidino  # noqa: F401
    from app import app, db, Order, Store, User
    from merchant_marketplace_v2 import SellerLedger, SellerOrder

    PaymentTransaction = app.extensions["kharidino_payment_transaction"]
    FinancialJournalEntry = app.extensions["kharidino_financial_journal"]
    RefundRecord = app.extensions["kharidino_refund_record"]
    SellerClawback = app.extensions["kharidino_seller_clawback"]
    SellerClawbackResolution = app.extensions["kharidino_seller_clawback_resolution"]
    from accounting import SellerSettlement, SellerSettlementAllocation

    with app.app_context():
        # Older financial tests used to remove a ledger before its allocation.
        # SQLite can then reuse that ledger id, leaving an orphan allocation
        # which incorrectly trips the allocation invariant for this fresh flow.
        # Remove only orphan allocation facts; never touch valid ledger data.
        db.session.execute(
            db.delete(SellerSettlementAllocation).where(
                ~SellerSettlementAllocation.ledger_id.in_(db.select(SellerLedger.id))
            )
        )
        db.session.commit()

        user = User(name="Flow Test", email="flow-test@example.invalid", password="x", role="admin")
        store = Store(name="Flow Store", active=True)
        db.session.add_all([user, store]); db.session.flush()
        order = Order(user_id=user.id, total=100_000, status="تأیید شد", customer_name="Flow Test", phone="09120000000", address="Test address")
        db.session.add(order); db.session.flush()
        seller_order = SellerOrder(order_id=order.id, store_id=store.id, status="delivered", subtotal=100_000, shipping_fee=0, platform_fee=5_000, seller_total=95_000)
        db.session.add(seller_order); db.session.flush()
        # Allocation is a reservation against an available ledger. The ledger
        # becomes paid only after the settlement is actually processed.
        ledger = SellerLedger(seller_order_id=seller_order.id, store_id=store.id, gross=100_000, shipping=0, platform_fee=5_000, net=95_000, status="available")
        db.session.add(ledger); db.session.flush()
        tx = PaymentTransaction(order_id=order.id, user_id=user.id, amount=100_000, status="paid", gateway="test", authority="FLOW-AUTH-1", idempotency_key="FLOW-IDEMP-1")
        db.session.add(tx); db.session.commit()

        expected_payment_refs = {f"PAYMENT:{tx.public_id}:CASH", f"PAYMENT:{tx.public_id}:SELLER", f"PAYMENT:{tx.public_id}:PLATFORM"}
        payment_refs = {x.reference for x in FinancialJournalEntry.query.filter(FinancialJournalEntry.reference.in_(expected_payment_refs)).all()}
        assert payment_refs == expected_payment_refs

        settlement = SellerSettlement(store_id=store.id, amount=95_000, status="requested", note="flow test", requested_by=user.id)
        db.session.add(settlement); db.session.flush()
        allocation = SellerSettlementAllocation(settlement_id=settlement.id, ledger_id=ledger.id, amount=95_000)
        db.session.add(allocation); db.session.flush()
        settlement.status = "paid"
        settlement.processed_by = user.id
        ledger.status = "paid"
        db.session.commit()

        from flask import session
        with app.test_request_context(f"/payment/refund/{tx.public_id}", method="POST"):
            session["user_id"] = user.id
            response = app.view_functions["payment_refund"](transaction_id=tx.public_id)
            assert response.status_code in {301, 302, 303, 307, 308}

        db.session.expire_all(); tx = db.session.get(PaymentTransaction, tx.id)
        refund = RefundRecord.query.filter_by(payment_transaction_id=tx.id).one(); clawbacks = SellerClawback.query.filter_by(refund_id=refund.id).all()
        assert tx.status == "refunded"; assert order.status == "لغو شد"; assert refund.status == "succeeded"
        assert len(clawbacks) == 1 and clawbacks[0].amount == 95_000
        assert settlement.status == "paid"
        assert SellerSettlementAllocation.query.filter_by(settlement_id=settlement.id).count() == 1

        expected_refund_refs = {f"REFUND:{tx.public_id}:CASH", f"REFUND:{tx.public_id}:SELLER", f"REFUND:{tx.public_id}:PLATFORM"}
        refund_refs = {x.reference for x in FinancialJournalEntry.query.filter(FinancialJournalEntry.reference.in_(expected_refund_refs)).all()}
        assert refund_refs == expected_refund_refs

        with app.test_request_context(f"/payment/refund/{tx.public_id}", method="POST"):
            session["user_id"] = user.id
            response = app.view_functions["payment_refund"](transaction_id=tx.public_id)
            assert response.status_code in {301, 302, 303, 307, 308}
        db.session.expire_all()
        assert RefundRecord.query.filter_by(payment_transaction_id=tx.id).count() == 1
        assert SellerClawback.query.filter_by(refund_id=refund.id).count() == 1
        assert FinancialJournalEntry.query.filter_by(reference=f"REFUND:{tx.public_id}:CASH").count() == 1

        clawback = clawbacks[0]
        db.session.add(SellerClawbackResolution(clawback_id=clawback.id, amount=95_000, reference="FLOW-CLAWBACK-RESOLUTION-1", processed_by=user.id)); db.session.commit()
        db.session.expire_all(); clawback = db.session.get(SellerClawback, clawback.id)
        assert clawback.status == "settled"
        assert SellerClawbackResolution.query.filter_by(reference="FLOW-CLAWBACK-RESOLUTION-1").count() == 1

        db.session.delete(clawback); db.session.delete(refund)
        for row in FinancialJournalEntry.query.filter(FinancialJournalEntry.reference.in_(expected_payment_refs | expected_refund_refs)).all(): db.session.delete(row)
        db.session.delete(tx)
        db.session.delete(allocation); db.session.delete(settlement)
        db.session.delete(ledger); db.session.delete(seller_order); db.session.delete(order); db.session.delete(store); db.session.delete(user); db.session.commit()
