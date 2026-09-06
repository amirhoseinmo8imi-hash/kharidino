"""Safely reset a local Kharidino admin password.

Usage:
    python reset_admin.py
    python reset_admin.py --email admin@kharidino.local --password 'YourNewPassword'

This utility changes the local database only. It does not expose or store a
password in source control. When no password is supplied, a strong random
password is generated and printed once to the terminal.
"""
from __future__ import annotations

import argparse
import secrets
import string

from app import app, db, User
from security_hardening import apply_security


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_="
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset a Kharidino admin password locally.")
    parser.add_argument("--email", default="", help="Admin email. Blank = use the first existing admin.")
    parser.add_argument("--password", default="", help="New password. Blank = generate a strong random password.")
    args = parser.parse_args()

    if args.password and len(args.password) < 12:
        parser.error("Password must be at least 12 characters.")

    with app.app_context():
        apply_security(app)
        admins = User.query.filter_by(role="admin").order_by(User.id.asc()).all()

        if not admins:
            print("No admin account exists in the current database.")
            print("Set KHARIDINO_ADMIN_EMAIL and KHARIDINO_ADMIN_PASSWORD, then run the launcher once.")
            return 2

        if args.email:
            admin = User.query.filter_by(email=args.email.strip().lower(), role="admin").first()
            if not admin:
                print(f"Admin account not found: {args.email}")
                print("Existing admin emails:")
                for item in admins:
                    print(f"  - {item.email}")
                return 3
        else:
            admin = admins[0]

        password = args.password or generate_password()
        admin.password = __import__("werkzeug.security", fromlist=["generate_password_hash"]).generate_password_hash(password)
        db.session.commit()

        print("==============================================")
        print("KHARIDINO ADMIN PASSWORD RESET")
        print("==============================================")
        print(f"Email:    {admin.email}")
        print(f"Password: {password}")
        print("==============================================")
        print("این رمز را در جای امن نگه دار و بعداً تغییرش بده.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
