from datetime import datetime
from flask import abort, flash, redirect, render_template, request, session, url_for
from pathlib import Path
import uuid
from werkzeug.utils import secure_filename

VEHICLE_CATEGORIES = ["خودرو سواری","موتورسیکلت","خودرو سنگین","ماشین‌آلات و تجهیزات","قایق و وسایل دریایی","قطعات و لوازم نقلیه"]
VEHICLE_STATUS_LABELS = {"pending":"در انتظار بررسی","approved":"منتشر شده","rejected":"رد شده","sold":"فروخته شد"}
ALLOWED_IMAGES = {"png","jpg","jpeg","webp","gif"}

def register_vehicle_marketplace(app, db, User, login_required, admin_required):
    class VehicleAd(db.Model):
        __tablename__ = "vehicle_ad"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
        title = db.Column(db.String(220), nullable=False)
        category = db.Column(db.String(50), nullable=False, default="خودرو سواری")
        city = db.Column(db.String(80), nullable=False, default="تهران")
        district = db.Column(db.String(120), default="")
        price = db.Column(db.Integer, default=0, nullable=False)
        negotiable = db.Column(db.Boolean, default=False, nullable=False)
        description = db.Column(db.Text, default="")
        phone = db.Column(db.String(40), default="")
        brand = db.Column(db.String(100), default="")
        model = db.Column(db.String(120), default="")
        year = db.Column(db.Integer, default=0)
        mileage = db.Column(db.Integer, default=0)
        fuel = db.Column(db.String(40), default="")
        gearbox = db.Column(db.String(40), default="")
        body_color = db.Column(db.String(50), default="")
        engine = db.Column(db.String(80), default="")
        accident_status = db.Column(db.String(80), default="")
        seller_type = db.Column(db.String(40), default="شخصی")
        image = db.Column(db.String(500), default="")
        gallery = db.Column(db.Text, default="")
        status = db.Column(db.String(30), default="pending", nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        user = db.relationship("User", backref=db.backref("vehicle_ads", lazy=True))

    upload_dir = Path(app.root_path) / "static" / "uploads" / "vehicles"
    upload_dir.mkdir(parents=True, exist_ok=True)

    def save_image(file):
        if not file or not file.filename: return ""
        name = secure_filename(file.filename)
        if not name or "." not in name: raise ValueError("نام فایل تصویر نامعتبر است.")
        ext = name.rsplit(".",1)[1].lower()
        if ext not in ALLOWED_IMAGES: raise ValueError("فرمت تصویر مجاز نیست.")
        unique = f"{uuid.uuid4().hex}.{ext}"
        file.save(upload_dir / unique)
        return f"uploads/vehicles/{unique}"

    def remove_files(ad):
        root=(Path(app.root_path)/"static").resolve()
        for path in (ad.gallery or "").split("|"):
            if not path.startswith("uploads/vehicles/"): continue
            target=(Path(app.root_path)/"static"/path).resolve()
            try: target.relative_to(root)
            except ValueError: continue
            try:
                if target.is_file(): target.unlink()
            except OSError: pass

    def is_admin():
        user=db.session.get(User,session["user_id"]) if session.get("user_id") else None
        return bool(user and user.role=="admin")

    @app.context_processor
    def vehicle_globals():
        return {"vehicle_count":VehicleAd.query.filter_by(status="approved").count(),"vehicle_categories":VEHICLE_CATEGORIES}

    @app.route("/vehicles")
    def vehicles():
        q=request.args.get("q","").strip()[:100]; category=request.args.get("category","").strip(); city=request.args.get("city","").strip()[:80]
        query=VehicleAd.query.filter_by(status="approved")
        if q:
            n=f"%{q}%"; query=query.filter(db.or_(VehicleAd.title.ilike(n),VehicleAd.brand.ilike(n),VehicleAd.model.ilike(n),VehicleAd.description.ilike(n)))
        if category in VEHICLE_CATEGORIES: query=query.filter_by(category=category)
        if city: query=query.filter(VehicleAd.city.ilike(f"%{city}%"))
        for field in ("fuel","gearbox","seller_type"):
            value=request.args.get(field,"").strip()
            if value: query=query.filter(getattr(VehicleAd,field)==value)
        for field in ("min_price","max_price","min_year","max_year"):
            try: value=max(0,int(request.args.get(field,"") or 0))
            except ValueError: value=0
            if value:
                col={"min_price":VehicleAd.price,"max_price":VehicleAd.price,"min_year":VehicleAd.year,"max_year":VehicleAd.year}[field]
                query=query.filter(col>=value if field.startswith("min_") else col<=value)
        sort=request.args.get("sort","newest")
        if sort=="price_low": query=query.order_by(VehicleAd.price.asc(),VehicleAd.id.desc())
        elif sort=="price_high": query=query.order_by(VehicleAd.price.desc(),VehicleAd.id.desc())
        elif sort=="year_high": query=query.order_by(VehicleAd.year.desc(),VehicleAd.id.desc())
        else: sort="newest"; query=query.order_by(VehicleAd.id.desc())
        filters={"q":q,"category":category,"city":city,"sort":sort}
        return render_template("vehicles.html",ads=query.limit(100).all(),filters=filters,vehicle_categories=VEHICLE_CATEGORIES,status_labels=VEHICLE_STATUS_LABELS)

    @app.route("/vehicle/<int:ad_id>")
    def vehicle_detail(ad_id):
        ad=VehicleAd.query.get_or_404(ad_id)
        if ad.status!="approved" and not (is_admin() or session.get("user_id")==ad.user_id): abort(404)
        return render_template("vehicle_detail.html",ad=ad,gallery=[x for x in (ad.gallery or "").split("|") if x],status_labels=VEHICLE_STATUS_LABELS)

    @app.route("/vehicles/post",methods=["GET","POST"])
    @login_required
    def vehicle_post():
        if request.method=="POST":
            title=request.form.get("title","").strip()[:220]; category=request.form.get("category","").strip(); city=request.form.get("city","").strip()[:80]; phone=request.form.get("phone","").strip()[:40]
            if not title or category not in VEHICLE_CATEGORIES or not city or not phone:
                flash("عنوان، دسته، شهر و شماره تماس الزامی است.","warning"); return render_template("vehicle_post.html",vehicle_categories=VEHICLE_CATEGORIES)
            def num(name):
                try: return max(0,int(request.form.get(name,"0") or 0))
                except ValueError: return 0
            paths=[]
            try:
                for f in request.files.getlist("images")[:8]:
                    p=save_image(f)
                    if p: paths.append(p)
            except ValueError as exc:
                flash(str(exc),"danger"); return render_template("vehicle_post.html",vehicle_categories=VEHICLE_CATEGORIES)
            ad=VehicleAd(user_id=session["user_id"],title=title,category=category,city=city,district=request.form.get("district","").strip()[:120],price=num("price"),negotiable=request.form.get("negotiable")=="1",description=request.form.get("description","").strip(),phone=phone,brand=request.form.get("brand","").strip()[:100],model=request.form.get("model","").strip()[:120],year=num("year"),mileage=num("mileage"),fuel=request.form.get("fuel","").strip()[:40],gearbox=request.form.get("gearbox","").strip()[:40],body_color=request.form.get("body_color","").strip()[:50],engine=request.form.get("engine","").strip()[:80],accident_status=request.form.get("accident_status","").strip()[:80],seller_type=request.form.get("seller_type","شخصی").strip()[:40],image=paths[0] if paths else "",gallery="|".join(paths),status="pending")
            db.session.add(ad); db.session.commit(); flash("آگهی ثبت شد و پس از بررسی مدیریت منتشر می‌شود.","success"); return redirect(url_for("my_vehicles"))
        return render_template("vehicle_post.html",vehicle_categories=VEHICLE_CATEGORIES)

    @app.route("/my-vehicles")
    @login_required
    def my_vehicles():
        return render_template("my_vehicles.html",ads=VehicleAd.query.filter_by(user_id=session["user_id"]).order_by(VehicleAd.id.desc()).all(),status_labels=VEHICLE_STATUS_LABELS)

    @app.post("/vehicle/<int:ad_id>/delete")
    @login_required
    def vehicle_delete(ad_id):
        ad=VehicleAd.query.get_or_404(ad_id)
        if ad.user_id!=session["user_id"] and not is_admin(): abort(403)
        remove_files(ad); db.session.delete(ad); db.session.commit(); flash("آگهی حذف شد.","success")
        return redirect(url_for("admin_vehicles") if is_admin() else url_for("my_vehicles"))

    @app.route("/admin/vehicles")
    @admin_required
    def admin_vehicles():
        status=request.args.get("status","").strip(); query=VehicleAd.query.order_by(VehicleAd.id.desc())
        if status in VEHICLE_STATUS_LABELS: query=query.filter_by(status=status)
        else: status=""
        return render_template("admin_vehicles.html",ads=query.all(),status=status,status_labels=VEHICLE_STATUS_LABELS)

    @app.post("/admin/vehicles/<int:ad_id>/status")
    @admin_required
    def admin_vehicle_status(ad_id):
        ad=VehicleAd.query.get_or_404(ad_id); status=request.form.get("status","").strip()
        if status not in VEHICLE_STATUS_LABELS: flash("وضعیت آگهی معتبر نیست.","danger")
        else: ad.status=status; db.session.commit(); flash("وضعیت آگهی به‌روزرسانی شد.","success")
        return redirect(url_for("admin_vehicles"))

    app.jinja_env.globals["vehicle_status_label"]=lambda s: VEHICLE_STATUS_LABELS.get(s,s)
    return VehicleAd
