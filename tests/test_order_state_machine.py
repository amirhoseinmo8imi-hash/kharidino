from order_state_machine import allowed_order_transition, ORDER_STATUS_FLOW


def test_master_order_happy_path():
    status = "در انتظار بررسی"
    for next_status in ["تأیید شد", "در حال آماده‌سازی", "ارسال شد", "تحویل شد"]:
        assert allowed_order_transition(status, next_status)
        status = next_status
    assert status == "تحویل شد"


def test_master_order_cannot_skip_states():
    assert not allowed_order_transition("در انتظار بررسی", "ارسال شد")
    assert not allowed_order_transition("تأیید شد", "تحویل شد")
    assert not allowed_order_transition("در حال آماده‌سازی", "تحویل شد")


def test_master_order_cancellation_rules():
    assert allowed_order_transition("در انتظار بررسی", "لغو شد")
    assert allowed_order_transition("تأیید شد", "لغو شد")
    assert allowed_order_transition("در حال آماده‌سازی", "لغو شد")
    assert not allowed_order_transition("ارسال شد", "لغو شد")
    assert not allowed_order_transition("تحویل شد", "لغو شد")
    assert not allowed_order_transition("لغو شد", "تأیید شد")


def test_terminal_states_have_no_outgoing_transitions():
    assert ORDER_STATUS_FLOW["تحویل شد"] == set()
    assert ORDER_STATUS_FLOW["لغو شد"] == set()
