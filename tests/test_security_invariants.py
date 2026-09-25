"""Regression tests for production security invariants."""
from security_hardening import _is_safe_local_redirect


def test_local_redirect_rejects_external_targets():
    assert not _is_safe_local_redirect("https://evil.example/")
    assert not _is_safe_local_redirect("//evil.example/")
    assert not _is_safe_local_redirect("\\\\evil.example\\")


def test_local_redirect_allows_relative_paths():
    assert _is_safe_local_redirect("/orders")
    assert _is_safe_local_redirect("/orders?status=paid")


def test_local_redirect_rejects_control_characters():
    assert not _is_safe_local_redirect("/orders\nLocation: https://evil.example")
