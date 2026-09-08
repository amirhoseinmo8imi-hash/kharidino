from financial_accounting import _money


def test_money_never_returns_negative():
    assert _money(100.4) == 100
    assert _money(-10) == 0
    assert _money(None) == 0


def test_payment_journal_math_balances():
    gross = 100_000
    seller_net = 95_000
    platform_fee = 5_000
    assert gross == seller_net + platform_fee


def test_refund_journal_reverses_original_amount():
    original = 250_000
    refund_cash = 250_000
    assert refund_cash == original
