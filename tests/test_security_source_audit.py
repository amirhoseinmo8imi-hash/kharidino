from security_source_audit import audit


def test_security_source_audit_has_no_high_risk_sinks():
    assert audit() == []
