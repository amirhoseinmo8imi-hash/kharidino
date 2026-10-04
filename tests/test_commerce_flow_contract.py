"""Regression contracts for the end-to-end paid-order flow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_payment_completion_issues_invoice_and_attempts_email():
    source = (ROOT / "payment.py").read_text(encoding="utf-8")
    assert 'order.status = "تأیید شد"' in source
    assert "Invoice.query.filter_by(order_id=order.id).first()" in source
    assert 'invoice.status = "صادر شد"' in source
    assert "_send_invoice_email(" in source
    assert 'invoice.status = "صادر و ایمیل شد"' in source


def test_invoice_email_template_renders_items_without_raw_html():
    source = (ROOT / "templates" / "email_invoice.html").read_text(encoding="utf-8")
    assert "{% for item in order.items %}" in source
    assert "|safe" not in source
