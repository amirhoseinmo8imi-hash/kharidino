from flask import render_template, request, session, redirect, url_for, flash, abort

def register_gaming_control(app, db, User):
    Meta = db.Model.registry._class_registry.get("GamingProductMeta")
    Seller = db.Model.registry._class_registry.get("GamingSellerProfile")
    Report = db.Model.registry._class_registry.get("GamingReport")

    @app.get("/admin/gaming-control")
    def gaming_control():
        uid = session.get("user_id")
        user = db.session.get(User, uid) if uid else None
        if not user or user.role != "admin":
            flash("دسترسی فقط برای مدیر سایت است.", "danger")
            return redirect(url_for("login"))
        stats = {
            "listings": Meta.query.count() if Meta else 0,
            "approved": Meta.query.filter_by(status="approved").count() if Meta else 0,
            "pending": Meta.query.filter_by(status="pending").count() if Meta else 0,
            "sellers": Seller.query.count() if Seller else 0,
            "reports": Report.query.filter_by(status="open").count() if Report else 0,
        }
        recent = Meta.query.order_by(Meta.id.desc()).limit(30).all() if Meta else []
        return render_template("gaming/control.html", stats=stats, recent=recent)

    @app.post("/admin/gaming-control/listing/<int:listing_id>")
    def gaming_control_listing(listing_id):
        uid = session.get("user_id")
        user = db.session.get(User, uid) if uid else None
        if not user or user.role != "admin": abort(403)
        meta = db.session.get(Meta, listing_id) if Meta else None
        if not meta: abort(404)
        meta.status = request.form.get("status", meta.status).strip()
        meta.seller_verified = request.form.get("seller_verified") == "1"
        db.session.commit()
        return redirect(url_for("gaming_control"))
