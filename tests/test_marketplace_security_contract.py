"""Regression contracts for seller-order isolation."""
from merchant_marketplace_v2 import STATUS_FLOW


def test_seller_order_flow_has_no_implicit_delivery_to_payment_release():
    assert STATUS_FLOW["shipped"] == {"delivered"}
    assert STATUS_FLOW["delivered"] == set()


def test_cancelled_seller_order_is_terminal():
    assert STATUS_FLOW["cancelled"] == set()
