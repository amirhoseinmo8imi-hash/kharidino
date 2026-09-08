from payment import DisabledGateway, PAYMENT_STATUSES, TestGateway, _idempotency_key, _gateway


def test_payment_statuses():
    assert {"pending", "redirect", "verifying", "paid", "failed", "cancelled", "refunded"} == PAYMENT_STATUSES


def test_idempotency_key_validation():
    assert _idempotency_key(" checkout-123 ") == "checkout-123"
    for value in (None, "", "   ", "x" * 129):
        try:
            _idempotency_key(value)
        except ValueError:
            continue
        assert False


def test_test_gateway_requires_approval():
    gateway = TestGateway()
    started = gateway.start("tx-1", 1000, "https://example.test/callback")
    assert started.status == "redirect"
    assert started.authority
    assert not gateway.verify("tx-1", 1000, {"authority": started.authority}).paid
    result = gateway.verify("tx-1", 1000, {"authority": started.authority, "approved": "1"})
    assert result.paid
    assert result.reference.startswith("TEST-")


def test_test_gateway_reference_is_deterministic_for_repeated_verification():
    gateway = TestGateway()
    started = gateway.start("tx-replay", 1000, "https://example.test/callback")
    payload = {"authority": started.authority, "approved": "1"}
    first = gateway.verify("tx-replay", 1000, payload)
    second = gateway.verify("tx-replay", 1000, payload)
    assert first.paid and second.paid
    assert first.reference == second.reference


def test_payment_route_contains_replay_and_concurrency_guards():
    source = __import__("pathlib").Path("payment.py").read_text(encoding="utf-8")
    callback = source[source.index('def payment_callback('):source.index('\n\n    @app.post("/payment/refund/', source.index('def payment_callback('))]
    assert 'if tx.status == "paid":' in callback
    assert 'if tx.status in {"cancelled", "refunded"}:' in callback
    assert 'PaymentTransaction.status.in_({"pending", "redirect", "failed"})' in callback
    assert '.update({"status": "verifying"}, synchronize_session=False)' in callback
    assert 'if claim != 1:' in callback
    assert 'PaymentTransaction.status == "verifying"' in callback
    assert 'failed_at": db.func.now()' in callback
    assert callback.index('db.session.commit()') < callback.index('result = gateway.verify(')


def test_payment_route_cannot_double_post_gateway_reference():
    source = __import__("pathlib").Path("payment.py").read_text(encoding="utf-8")
    model_start = source.index("class PaymentTransaction(")
    model_end = source.index('\n\n    app.extensions["kharidino_payment_transaction"]', model_start)
    model = source[model_start:model_end]
    assert 'authority = db.Column(db.String(200), unique=True' in model
    assert 'gateway_reference = db.Column(db.String(200), unique=True' in model
    assert 'idempotency_key = db.Column(db.String(128), unique=True' in model


def test_payment_e2e_contract_connects_checkout_to_testgateway_callback_and_paid_order():
    source = __import__("pathlib").Path("payment.py").read_text(encoding="utf-8")
    assert 'app.view_functions["checkout"] = checkout_payment_wrapper' in source
    assert 'session["checkout_payment_order_id"] = new_orders[0].id' in source
    assert 'url_for("payment_start_form", order_id=order.id)' in source
    assert 'if os.environ.get("PAYMENT_TEST_MODE", "0").lower() in {"1", "true", "yes"}:' in source
    assert 'return TestGateway()' in source
    assert 'gateway.start(tx.public_id, tx.amount' in source
    assert 'tx.authority = result.authority' in source
    assert 'gateway.verify(tx.public_id, tx.amount, request.values.to_dict())' in source
    assert 'tx.status = "paid"' in source
    assert 'order.status = "تأیید شد"' in source


def test_test_mode_never_falls_through_to_real_provider(monkeypatch):
    monkeypatch.setenv("PAYMENT_TEST_MODE", "1")
    monkeypatch.setenv("PAYMENT_PROVIDER", "nextpay")
    assert isinstance(_gateway(), TestGateway)


def test_production_default_gateway_is_disabled(monkeypatch):
    monkeypatch.delenv("PAYMENT_TEST_MODE", raising=False)
    monkeypatch.delenv("PAYMENT_PROVIDER", raising=False)
    gateway = _gateway()
    assert isinstance(gateway, DisabledGateway)
    started = gateway.start("tx-prod", 1000, "https://example.test/callback")
    assert started.status == "failed"
    assert not gateway.verify("tx-prod", 1000, {}).paid


def test_test_mode_is_explicit(monkeypatch):
    monkeypatch.setenv("PAYMENT_TEST_MODE", "true")
    assert isinstance(_gateway(), TestGateway)
    monkeypatch.setenv("PAYMENT_TEST_MODE", "0")
    assert isinstance(_gateway(), DisabledGateway)


def test_payment_callback_secret_never_has_a_usable_fallback(monkeypatch):
    monkeypatch.delenv("PAYMENT_CALLBACK_SECRET", raising=False)
    from payment import _valid_callback_signature

    assert not _valid_callback_signature("tx-prod", "anything")
