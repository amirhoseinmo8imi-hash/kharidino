"""Secure local admin password reset utility.

Usage on Windows (from the Kharidino project directory):
    set KHARIDINO_ADMIN_EMAIL=admin@example.com
    set KHARIDINO_ADMIN_PASSWORD=choose-a-long-random-password
    python scripts\\reset_admin.py

The credentials are read only from environment variables and are never
written to source control by this script.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app, db, User
from werkzeug.security import generate_password_hash


def main():
    email = os.environ.get("KHARIDINO_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("KHARIDINO_ADMIN_PASSWORD", "")

    if not email or not password:
        raise SystemExit(
            "Set KHARIDINO_ADMIN_EMAIL and KHARIDINO_ADMIN_PASSWORD first."
        )

    if len(password) < 12:
        raise SystemExit("Admin password must be at least 12 characters.")

    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if user is None:
            user = User(
                name="مدیر سایت",
                email=email,
                password=generate_password_hash(password),
                role="admin",
            )
            db.session.add(user)
            action = "created"
        else:
            user.password = generate_password_hash(password)
            user.role = "admin"
            action = "updated"

        db.session.commit()

        print(f"Admin account {action}: {email}")
        print("Password has been hashed and saved to the local database.")
        print("The plaintext password was not written to the project.")


if __name__ == "__main__":
    main()
