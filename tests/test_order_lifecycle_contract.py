from order_state_machine import ORDER_STATUS_FLOW, allowed_order_transition
from payment import PAYMENT_STATUSES, TestGateway


def test_order_lifecycle_is_forward_only_and_terminal():
    assert allowed_order_transition("در انتظار بررسی", "تأیید شد")
    assert allowed_order_transition("تأیید شد", "در حال آماده‌سازی")
    assert allowed_order_transition("در حال آماده‌سازی", "ارسال شد")
    assert allowed_order_transition("ارسال شد", "تحویل شد")
    assert not allowed_order_transition("تحویل شد", "لغو شد")
    assert not allowed_order_transition("ارسال شد", "در انتظار بررسی")
    assert ORDER_STATUS_FLOW["تحویل شد"] == set()
    assert ORDER_STATUS_FLOW["لغو شد"] == set()


def test_payment_test_gateway_requires_matching_authority_and_approval():
    gateway = TestGateway()
    started = gateway.start("tx-e2e", 125000, "https://example.test/callback")
    assert started.status == "redirect"
    assert started.authority

    assert not gateway.verify(
        "tx-e2e", 125000, {"authority": "wrong", "approved": "1"}
    ).paid
    assert not gateway.verify(
        "tx-e2e", 125000, {"authority": started.authority}
    ).paid

    verified = gateway.verify(
        "tx-e2e", 125000,
        {"authority": started.authority, "approved": "1"},
    )
    assert verified.paid
    assert verified.reference.startswith("TEST-")
    assert "paid" in PAYMENT_STATUSES
    assert "refunded" in PAYMENT_STATUSES
