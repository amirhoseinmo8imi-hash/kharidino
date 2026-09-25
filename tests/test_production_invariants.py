"""Regression tests for commerce invariants that must hold in production."""
from financial_accounting import _money
from merchant_marketplace_v2 import STATUS_FLOW
from payment import PAYMENT_STATUSES


def test_master_order_delivery_is_the_only_fund_release_trigger():
    assert "delivered" not in STATUS_FLOW["shipped"] or STATUS_FLOW["shipped"] == {"delivered"}
    assert STATUS_FLOW["delivered"] == set()
    assert STATUS_FLOW["cancelled"] == set()


def test_seller_order_cannot_skip_operational_states():
    assert STATUS_FLOW["new"] == {"confirmed", "cancelled"}
    assert STATUS_FLOW["confirmed"] == {"preparing", "cancelled"}
    assert STATUS_FLOW["preparing"] == {"shipped", "cancelled"}
    assert STATUS_FLOW["shipped"] == {"delivered"}


def test_payment_lifecycle_contains_terminal_refund_state():
    assert "paid" in PAYMENT_STATUSES
    assert "refunded" in PAYMENT_STATUSES
    assert "cancelled" in PAYMENT_STATUSES


def test_financial_amounts_are_never_negative():
    for value in (-1, -100000, None, 0):
        assert _money(value) >= 0
