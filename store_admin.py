"""Admin store management routes for Kharidino.

Kept in a small registration module so the core app.py does not need to be
rewritten just to add the store editor. The routes are registered against the
same Flask application and database/models.
"""

from flask import flash, redirect, render_template, request, url_for


def register(app, db, Store, admin_required, save_store_logo, remove_upload):
    """Register the admin store editor route."""

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

            new_logo = ""
            try:
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

    # Replace the public management page with an admin-only management page.
    # The existing endpoint remains `stores`, so existing navigation keeps working.
    view = app.view_functions.get("stores")
    if view is not None and not getattr(view, "_kharidino_store_admin_wrapped", False):
        protected_view = admin_required(view)
        protected_view._kharidino_store_admin_wrapped = True
        app.view_functions["stores"] = protected_view
