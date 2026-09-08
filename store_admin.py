"""Admin store management routes for Kharidino."""

from functools import wraps

from flask import flash, redirect, render_template, request, url_for


def register(app, db, Store, admin_required, save_store_logo, remove_upload):
    """Register the admin store editor and protect the store manager."""

    @app.route("/admin/store/edit/<int:store_id>", methods=["GET", "POST"])
    @admin_required
    def edit_store(store_id):
        store = Store.query.get_or_404(store_id)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            website = request.form.get("website", "").strip()
            active = request.form.get("active") == "1"
            remove_logo = request.form.get("remove_logo") == "1"
            old_logo = store.logo or ""

            if not name:
                flash("نام فروشگاه الزامی است.", "warning")
                return render_template("edit_store.html", store=store)

            try:
                new_logo = ""
                uploaded_logo = request.files.get("logo")
                if uploaded_logo and uploaded_logo.filename:
                    new_logo = save_store_logo(uploaded_logo)

                store.name = name
                store.website = website
                store.active = active

                if new_logo:
                    store.logo = new_logo
                    if old_logo:
                        remove_upload(old_logo)
                elif remove_logo and old_logo:
                    store.logo = ""
                    remove_upload(old_logo)

                db.session.commit()
                flash("اطلاعات فروشگاه با موفقیت به‌روزرسانی شد. ✅", "success")
                return redirect(url_for("stores"))

            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except Exception:
                db.session.rollback()
                flash("خطا هنگام ذخیره اطلاعات فروشگاه.", "danger")

        return render_template("edit_store.html", store=store)

    # The existing /stores route is the admin management screen. Keep its
    # endpoint name unchanged so all existing navigation remains valid, but
    # replace its view with an admin-only version that lists inactive stores too.
    original_stores_view = app.view_functions.get("stores")

    if original_stores_view is not None:
        @wraps(original_stores_view)
        @admin_required
        def protected_stores(*args, **kwargs):
            stores = Store.query.order_by(Store.name.asc()).all()
            return render_template("stores.html", stores=stores)

        app.view_functions["stores"] = protected_stores
