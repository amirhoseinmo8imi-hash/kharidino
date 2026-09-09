"""Recommended launcher for Kharidino Ultimate."""
import os
import socket
from pathlib import Path
from zipfile import ZipFile

from flask import redirect, request, render_template, url_for

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
PRODUCTS_DIR = BASE_DIR / "static" / "uploads" / "products"
PRODUCTS_ARCHIVE = PRODUCTS_DIR / "products.zip"


def _install_bundled_product_images():
    """Extract products.zip placed inside static/uploads/products safely."""
    if not PRODUCTS_ARCHIVE.is_file():
        return
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    root = PRODUCTS_DIR.resolve()
    extracted = 0
    try:
        with ZipFile(PRODUCTS_ARCHIVE) as archive:
            for info in archive.infolist():
                name = info.filename.replace("\\", "/").lstrip("/")
                parts = [part for part in name.split("/") if part not in {"", "."}]
                if parts and parts[0].lower() == "products":
                    parts = parts[1:]
                if not parts:
                    continue
                target = (PRODUCTS_DIR / Path(*parts)).resolve()
                if root != target and root not in target.parents:
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with archive.open(info) as src, target.open("wb") as dst:
                        dst.write(src.read())
                    extracted += 1
        if extracted:
            print(f"[Kharidino] Installed {extracted} bundled product image files.")
    except Exception as exc:
        print(f"[Kharidino] Product image archive was not installed: {exc}")


_install_bundled_product_images()

from app import app, db, Product, Category, Store, Offer, User, admin_required
from kharidino_ai import register as register_ai
from mobile_app.api.mobile_api import register_mobile_api
from security_hardening import apply_security
from redirect_hardening import apply_redirect_hardening
from catalog_security import apply_catalog_security
from catalog_ux_api import apply_catalog_ux_api
from inventory_hardening import apply_inventory_security
from checkout_preflight import apply_checkout_preflight
from checkout_idempotency import apply_checkout_idempotency
from commerce_extensions_v2 import apply_commerce_extensions
from commerce_catalog import apply_catalog_extensions
from order_state_machine import apply_order_state_machine
from payment import apply_payment
from button_flow_hardening import apply_button_flow_hardening
from refund_settlement_hardening import apply_refund_settlement_hardening
import commerce_runtime  # noqa: F401
import profile_extensions  # noqa: F401
import merchant_marketplace  # noqa: F401
import merchant_approval  # noqa: F401
import merchant_marketplace_v2  # noqa: F401
import merchant_customer_marketplace  # noqa: F401
import seller_storefront  # noqa: F401 - public seller storefront
import seller_introduction  # noqa: F401 - seller acquisition landing page
import terms  # noqa: F401 - public terms and conditions page
import password_reset  # noqa: F401 - password recovery and reset
import accounting  # noqa: F401 - platform and seller accounting workspace
import system_health  # noqa: F401 - deployment and consistency probes
from inventory_atomicity import apply_inventory_atomicity
from financial_accounting import apply_financial_accounting

register_ai(app, db, Product, Store, Offer, User, admin_required)
register_mobile_api(app, db, Product, Category, Store, Offer)

with app.app_context():
    apply_security(app)
    apply_redirect_hardening(app)
    apply_catalog_security(app)
    apply_catalog_ux_api(app, db, Product, Category, Offer, Store)
    apply_checkout_preflight(app)
    apply_checkout_idempotency(app, db)
    apply_inventory_security(app)
    apply_inventory_atomicity(app)
    apply_order_state_machine(app)
    apply_commerce_extensions(app)
    apply_catalog_extensions(app)
    apply_payment(app, db, __import__("app").Order, User)
    from merchant_marketplace_v2 import SellerLedger, SellerOrder
    from accounting import SellerSettlement, SellerSettlementAllocation
    PaymentTransaction = app.extensions["kharidino_payment_transaction"]
    apply_financial_accounting(app, db, __import__("app").Order, SellerLedger, SellerSettlement)
    apply_refund_settlement_hardening(
        app, db, __import__("app").Order, PaymentTransaction, SellerOrder,
        SellerLedger, SellerSettlement, SellerSettlementAllocation,
    )
    apply_button_flow_hardening(app, db, Store, User)
    db.create_all()


def _port_is_available(host: str, port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.25)
    try:
        result = probe.connect_ex(("127.0.0.1", port))
        return result != 0
    except OSError:
        return True
    finally:
        probe.close()


def _select_port(requested: int) -> int:
    if _port_is_available("0.0.0.0", requested):
        return requested
    if os.environ.get("STRICT_PORT", "0").lower() in {"1", "true", "yes"}:
        raise RuntimeError(f"Port {requested} is already in use. Stop the old Kharidino server or choose another PORT.")
    for candidate in range(requested + 1, requested + 21):
        if _port_is_available("0.0.0.0", candidate):
            return candidate
    raise RuntimeError("No free port found.")


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = _select_port(int(os.environ.get("PORT", "5000")))
    print(f"[Kharidino] Running on http://{host}:{port}")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")