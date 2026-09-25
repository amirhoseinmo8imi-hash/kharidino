"""Production-oriented health and consistency checks for Kharidino."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import jsonify, render_template
from sqlalchemy import inspect, text

from app import app, db, admin_required


def _check_database():
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            dialect = connection.dialect.name
            integrity = "ok"
            if dialect == "sqlite":
                integrity = connection.execute(text("PRAGMA integrity_check")).scalar() or "unknown"
        return {"ok": integrity == "ok", "integrity": integrity}
    except Exception as exc:
        app.logger.exception("Database health check failed")
        return {"ok": False, "integrity": "error", "error": type(exc).__name__}


def _check_schema():
    required = {
        "user", "product", "store", "offer", "order", "order_item",
        "kharidino_product_inventory", "kharidino_inventory_reservation",
        "kharidino_seller_order", "kharidino_seller_order_item",
        "kharidino_seller_ledger", "kharidino_seller_notification",
        "kharidino_accounting_expense", "kharidino_seller_settlement",
    }
    try:
        tables = set(inspect(db.engine).get_table_names())
        missing = sorted(required - tables)
        return {"ok": not missing, "missing": missing, "table_count": len(tables)}
    except Exception as exc:
        app.logger.exception("Schema health check failed")
        return {"ok": False, "missing": [], "table_count": 0, "error": type(exc).__name__}


def _check_data_consistency():
    checks = []
    queries = [
        ("negative_inventory", "SELECT COUNT(*) FROM kharidino_product_inventory WHERE quantity < 0"),
        ("negative_ledger", "SELECT COUNT(*) FROM kharidino_seller_ledger WHERE gross < 0 OR platform_fee < 0 OR net < 0"),
        ("orphan_seller_orders", "SELECT COUNT(*) FROM kharidino_seller_order so LEFT JOIN store s ON s.id = so.store_id WHERE s.id IS NULL"),
        ("orphan_ledger", "SELECT COUNT(*) FROM kharidino_seller_ledger sl LEFT JOIN kharidino_seller_order so ON so.id = sl.seller_order_id WHERE so.id IS NULL"),
    ]
    try:
        with db.engine.connect() as connection:
            for name, query in queries:
                value = int(connection.execute(text(query)).scalar() or 0)
                checks.append({"name": name, "count": value, "ok": value == 0})
        return {"ok": all(item["ok"] for item in checks), "checks": checks}
    except Exception as exc:
        app.logger.exception("Data consistency check failed")
        return {"ok": False, "checks": [], "error": type(exc).__name__}


def _snapshot():
    database = _check_database()
    schema = _check_schema()
    consistency = _check_data_consistency()
    return {
        "status": "healthy" if database["ok"] and schema["ok"] and consistency["ok"] else "attention",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": database,
        "schema": schema,
        "consistency": consistency,
    }


@app.get("/healthz")
def healthz():
    """Minimal deployment probe; never exposes schema or row counts."""
    database = _check_database()
    if not database["ok"]:
        return jsonify({"status": "unhealthy"}), 503
    return jsonify({"status": "healthy"})


@app.get("/admin/system-health")
@admin_required
def admin_system_health():
    return render_template("system_health.html", health=_snapshot())
