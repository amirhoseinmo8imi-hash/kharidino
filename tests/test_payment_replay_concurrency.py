"""Replay and database-concurrency regression contracts for payments.

These tests deliberately use no external gateway and no credentials. The
SQLite race test exercises the same conditional state-claim pattern used by
payment.py, while the source contracts lock the production lifecycle rules.
"""
from pathlib import Path
import sqlite3
import threading

ROOT = Path(__file__).resolve().parents[1]


def _payment_source():
    return (ROOT / "payment.py").read_text(encoding="utf-8")


def _callback_block():
    source = _payment_source()
    start = source.index("def payment_callback(")
    end = source.index('\n\n    @app.post("/payment/refund/', start)
    return source[start:end]


def test_replay_after_paid_is_terminal_and_does_not_verify_again():
    block = _callback_block()
    assert 'if tx.status == "paid":' in block
    assert block.index('if tx.status == "paid":') < block.index('result = gateway.verify(')


def test_replay_after_refunded_is_terminal():
    block = _callback_block()
    assert 'if tx.status in {"cancelled", "refunded"}:' in block
    assert block.index('if tx.status in {"cancelled", "refunded"}:') < block.index('result = gateway.verify(')


def test_failed_payment_can_retry_with_same_bound_authority():
    block = _callback_block()
    assert 'PaymentTransaction.status.in_({"pending", "redirect", "failed"})' in block
    assert 'PaymentTransaction.status == "verifying"' in block
    assert '"failed_at": db.func.now()' in block
    assert 'hmac.compare_digest(tx.authority, returned_authority)' in block


def test_successful_replay_cannot_insert_a_second_gateway_reference():
    source = _payment_source()
    assert 'gateway_reference = db.Column(db.String(200), unique=True' in source
    block = _callback_block()
    assert 'tx.gateway_reference = result.reference[:200]' in block
    assert 'except IntegrityError:' in block


def test_callback_claim_is_conditional_and_committed_before_verify():
    block = _callback_block()
    claim_text = 'PaymentTransaction.query.filter(\n            PaymentTransaction.id == tx.id,\n            PaymentTransaction.status.in_({"pending", "redirect", "failed"}),\n        ).update({"status": "verifying"}, synchronize_session=False)'
    assert claim_text in block
    assert block.index('db.session.commit()') < block.index('result = gateway.verify(')


def test_concurrent_sqlite_claim_allows_exactly_one_verifier(tmp_path):
    """Two real DB connections must yield one claim and one no-op."""
    db_path = tmp_path / "payment-race.sqlite3"
    keeper = sqlite3.connect(db_path, check_same_thread=False)
    keeper.execute(
        "CREATE TABLE payment_transaction "
        "(id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
    )
    keeper.execute(
        "INSERT INTO payment_transaction(id, status) VALUES (1, 'redirect')"
    )
    keeper.commit()
    keeper.close()

    barrier = threading.Barrier(2)
    results = []
    errors = []
    lock = threading.Lock()

    def worker():
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
        try:
            barrier.wait(timeout=5)
            cursor = conn.execute(
                "UPDATE payment_transaction SET status='verifying' "
                "WHERE id=? AND status IN ('pending','redirect','failed')",
                (1,),
            )
            claimed = cursor.rowcount == 1
            conn.commit()
            with lock:
                results.append(claimed)
        except Exception as exc:  # pragma: no cover - assertion below reports it
            with lock:
                errors.append(exc)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(results) == [False, True]

    verifier = sqlite3.connect(db_path)
    try:
        assert (
            verifier.execute(
                "SELECT status FROM payment_transaction WHERE id=1"
            ).fetchone()[0]
            == "verifying"
        )
    finally:
        verifier.close()


def test_order_is_marked_paid_only_after_successful_gateway_verification():
    block = _callback_block()
    verify_index = block.index('result = gateway.verify(')
    paid_index = block.index('tx.status = "paid"')
    order_index = block.index('order.status = "تأیید شد"')
    assert verify_index < paid_index < order_index


def test_e2e_contract_keeps_provider_off_for_test_gateway_runs():
    source = _payment_source()
    assert 'PAYMENT_TEST_MODE' in source
    assert 'return TestGateway()' in source
    assert 'provider == "nextpay"' in source
    assert 'return DisabledGateway()' in source


def test_no_provider_credentials_are_embedded_in_replay_concurrency_tests():
    """Regression guard: this test module must contain no provider secret."""
    test_source = Path(__file__).read_text(encoding="utf-8")
    forbidden = ("_API_", "api_key")
    assert not any(token.lower() in test_source.lower() for token in forbidden)
