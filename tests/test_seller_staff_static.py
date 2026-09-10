from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_seller_staff_is_store_scoped_and_role_limited():
    src = (ROOT / "seller_staff.py").read_text(encoding="utf-8")
    assert "store_id=account.store_id" in src
    assert "VALID_ROLES" in src
    assert '"all"' in src
    assert "role not in VALID_ROLES" in src


def test_seller_staff_revocation_is_soft_for_auditability():
    src = (ROOT / "seller_staff.py").read_text(encoding="utf-8")
    assert "row.active = False" in src
    assert "db.session.delete(row)" not in src


def test_launcher_activates_seller_staff_before_payment():
    src = (ROOT / "run_kharidino.py").read_text(encoding="utf-8")
    assert "from seller_staff import apply_seller_staff" in src
    assert src.index("apply_seller_staff(app)") < src.index("apply_payment(app")
