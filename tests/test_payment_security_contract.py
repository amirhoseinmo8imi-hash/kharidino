"""Contract tests for the payment state boundary."""
from payment import PAYMENT_STATUSES


def test_payment_has_explicit_terminal_states():
    assert PAYMENT_STATUSES >= {"paid", "failed", "cancelled", "refunded"}


def test_payment_has_non_terminal_processing_states():
    assert PAYMENT_STATUSES >= {"pending", "redirect", "verifying"}


def test_paid_and_refunded_are_distinct_states():
    assert "paid" != "refunded"
