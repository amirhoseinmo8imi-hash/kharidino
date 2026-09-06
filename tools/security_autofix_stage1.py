from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    original = text

    # Strong runtime secret: never fall back to a known/static Flask secret.
    text = replace_once(
        text,
        'import os\nimport uuid\n',
        'import os\nimport secrets\nimport uuid\n',
        "imports",
    )
    text = replace_once(
        text,
        'app.config["SECRET_KEY"] = os.environ.get(\n    "SECRET_KEY",\n    "change-this-secret-key"\n)\n',
        'configured_secret = os.environ.get("SECRET_KEY", "").strip()\nif configured_secret:\n    app.config["SECRET_KEY"] = configured_secret\nelse:\n    app.config["SECRET_KEY"] = secrets.token_urlsafe(48)\n',
        "secret fallback",
    )

    # Open-redirect protection for compare return targets.
    text = replace_once(
        text,
        'from pathlib import Path\n\nfrom flask import (',
        'from pathlib import Path\nfrom urllib.parse import urlparse\n\nfrom flask import (',
        "urlparse import",
    )
    marker = '# =========================================================\n# FILE HELPERS\n# =========================================================\n'
    helper = '''# =========================================================\n# SAFE REDIRECTS\n# =========================================================\n\ndef safe_local_redirect(target, fallback):\n    target = (target or "").strip()\n    if not target:\n        return fallback\n    parsed = urlparse(target)\n    if (\n        target.startswith("/")\n        and not target.startswith("//")\n        and not parsed.scheme\n        and not parsed.netloc\n        and not parsed.username\n        and not parsed.password\n    ):\n        return target\n    return fallback\n\n\n'''
    text = replace_once(text, marker, helper + marker, "safe redirect helper")
    text = replace_once(
        text,
        'target = request.form.get("next") or request.referrer or url_for("home")\n    return redirect(target)\n',
        'fallback = url_for("home")\n    target = safe_local_redirect(request.form.get("next"), fallback)\n    if target == fallback and request.referrer:\n        target = safe_local_redirect(request.referrer, fallback)\n    return redirect(target)\n',
        "compare redirect",
    )

    # Logout is a state-changing action: require POST so CSRF protection applies.
    text = replace_once(
        text,
        '@app.route("/logout")\ndef logout():\n',
        '@app.post("/logout")\ndef logout():\n',
        "logout method",
    )

    # Do not leak raw exception objects to administrators/users.
    text = replace_once(
        text,
        '    except Exception as e:\n\n        db.session.rollback()\n\n        flash(\n            f"خطا هنگام تعمیر پیشنهادها: {e}",\n            "danger"\n        )\n',
        '    except Exception:\n\n        db.session.rollback()\n        app.logger.exception("admin_fix_offers failed")\n\n        flash(\n            "تعمیر پیشنهادها با خطا مواجه شد.",\n            "danger"\n        )\n',
        "admin exception disclosure",
    )

    # Validate external store/offer URLs before persisting them.
    url_helper = '''def validate_external_url(value):\n    value = (value or "").strip()\n    if not value:\n        return ""\n    parsed = urlparse(value)\n    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:\n        raise ValueError("لینک باید یک آدرس معتبر http یا https باشد.")\n    if parsed.username or parsed.password:\n        raise ValueError("لینک‌های دارای نام کاربری یا رمز عبور مجاز نیستند.")\n    return value\n\n\n'''
    text = replace_once(text, marker, url_helper + marker, "URL validator")
    text = replace_once(
        text,
        '    store.website = request.form.get(\n        "website",\n        ""\n    ).strip()\n',
        '    try:\n        store.website = validate_external_url(request.form.get("website", ""))\n    except ValueError as exc:\n        db.session.rollback()\n        flash(str(exc), "danger")\n        return redirect(url_for("admin") + "#stores-admin")\n',
        "store URL validation",
    )
    text = replace_once(
        text,
        '    offer.url = request.form.get(\n        "url",\n        ""\n    ).strip()\n',
        '    try:\n        offer.url = validate_external_url(request.form.get("url", ""))\n    except ValueError as exc:\n        db.session.rollback()\n        flash(str(exc), "danger")\n        return redirect(url_for("admin") + "#offers-admin")\n',
        "offer URL validation",
    )

    # Never bootstrap a known admin password. Require explicit environment input.
    old_admin = '''    if not admin:\n\n        db.session.add(\n            User(\n                name="مدیر سایت",\n                email="admin@kharidino.local",\n                password=generate_password_hash(\n                    "admin12345"\n                ),\n                role="admin"\n            )\n        )\n'''
    new_admin = '''    if not admin:\n\n        bootstrap_email = os.environ.get("KHARIDINO_ADMIN_EMAIL", "").strip().lower()\n        bootstrap_password = os.environ.get("KHARIDINO_ADMIN_PASSWORD", "")\n        if bootstrap_email and bootstrap_password:\n            if len(bootstrap_password) < 12:\n                raise RuntimeError("KHARIDINO_ADMIN_PASSWORD must be at least 12 characters.")\n            db.session.add(\n                User(\n                    name="مدیر سایت",\n                    email=bootstrap_email,\n                    password=generate_password_hash(bootstrap_password),\n                    role="admin"\n                )\n            )\n'''
    text = replace_once(text, old_admin, new_admin, "bootstrap admin password")

    # Development server must not enable Flask debugger by default.
    text = replace_once(
        text,
        '        debug=True\n',
        '        debug=os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}\n',
        "debug mode",
    )

    if text == original:
        raise RuntimeError("No source changes were produced")
    APP.write_text(text, encoding="utf-8")
    print("Stage 1 security autofix applied to app.py")


if __name__ == "__main__":
    main()
