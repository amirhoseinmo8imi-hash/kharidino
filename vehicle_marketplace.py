from datetime import datetime
from flask import abort, flash, redirect, render_template, request, session, url_for
from pathlib import Path
import uuid
from werkzeug.utils import secure_filename

VEHICLE_CATEGORIES = ["خودرو سواری","موتورسیکلت","خودرو سنگین","ماشین‌آلات و تجهیزات","قایق و وسایل دریایی","قطعات و لوازم نقلیه"]
VEHICLE_STATUS_LABELS = {"pending":"در انتظار بررسی","approved":"منتشر شده","rejected":"رد شده","sold":"فروخته شد"}
ALLOWED_IMAGES = {"png","jpg","jpeg","webp","gif"}
VehicleAdModel = None

DEMO_VEHICLE_IMAGES = {
    "car": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=1000&q=82",
    "car2": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1000&q=82",
    "car3": "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=1000&q=82",
    "motorcycle": "https://images.unsplash.com/photo-1558981806-ec527fa84c39?auto=format&fit=crop&w=1000&q=82",
    "boat": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1000&q=82",
    "machine": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=1000&q=82",
    "parts": "https://images.unsplash.com/photo-1486006920555-c77dcf18193c?auto=format&fit=crop&w=1000&q=82",
}

def register_vehicle_marketplace(app, db, User, login_required, admin_required):
    global VehicleAdModel
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

    VehicleAdModel = VehicleAd
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


def seed_demo_vehicle_ads(db, User):
    """Create a diverse set of approved demo classifieds for a fresh local catalog.
    Images are loaded from stable Unsplash image URLs and are used only when the
    vehicle catalog is empty.
    """
    if VehicleAdModel is None or VehicleAdModel.query.count():
        return 0

    owner = User.query.filter_by(role="admin").order_by(User.id.asc()).first()
    if not owner:
        owner = User.query.order_by(User.id.asc()).first()
    if not owner:
        return 0

    rows = [
        ("پژو 207 اتوماتیک پانوراما", "خودرو سواری", "تهران", "سعادت‌آباد", 1180000000, "پژو", "207", 1402, 28000, "بنزین", "اتوماتیک", "سفید", "TU5", "بدون تصادف", "شخصی", "car"),
        ("دنا پلاس توربو اتومات", "خودرو سواری", "مشهد", "احمدآباد", 1045000000, "دنا", "پلاس توربو", 1401, 41000, "بنزین", "اتوماتیک", "مشکی", "EF7 Turbo", "بدون تصادف", "شخصی", "car2"),
        ("سمند LX تمیز و کم‌کار", "خودرو سواری", "اصفهان", "مرداویج", 690000000, "سمند", "LX", 1399, 76000, "بنزین", "دستی", "نقره‌ای", "EF7", "یک لکه رنگ", "شخصی", "car3"),
        ("هیوندای النترا مدل 2018", "خودرو سواری", "شیراز", "معالی‌آباد", 2380000000, "هیوندای", "النترا", 1397, 93000, "بنزین", "اتوماتیک", "قرمز", "2.0", "بدون تصادف", "نمایشگاه", "car2"),
        ("کیا سراتو مونتاژ آپشنال", "خودرو سواری", "تبریز", "ولیعصر", 1560000000, "کیا", "سراتو", 1398, 68000, "بنزین", "اتوماتیک", "سفید", "2.0", "بدون تصادف", "نمایشگاه", "car3"),

        ("موتورسیکلت هوندا 125 سالم", "موتورسیکلت", "تهران", "تهرانپارس", 185000000, "هوندا", "125", 1401, 19000, "بنزین", "دستی", "مشکی", "125cc", "بدون تصادف", "شخصی", "motorcycle"),
        ("بنلی 249 دو سیلندر", "موتورسیکلت", "کرج", "گوهردشت", 420000000, "بنلی", "249", 1402, 12000, "بنزین", "دستی", "قرمز", "249cc", "بدون تصادف", "شخصی", "motorcycle"),
        ("باجاج پالس NS200", "موتورسیکلت", "رشت", "گلسار", 315000000, "باجاج", "NS200", 1400, 24000, "بنزین", "دستی", "مشکی", "200cc", "بدون تصادف", "شخصی", "motorcycle"),
        ("کویر موتور 150 شهری", "موتورسیکلت", "قم", "صفائیه", 145000000, "کویر", "150", 1399, 31000, "بنزین", "دستی", "آبی", "150cc", "یک لکه رنگ", "شخصی", "motorcycle"),
        ("وسپا Primavera کارکرده", "موتورسیکلت", "اهواز", "کیانپارس", 610000000, "وسپا", "Primavera", 1401, 9000, "بنزین", "اتوماتیک", "سبز", "150cc", "بدون تصادف", "شخصی", "motorcycle"),

        ("کشنده ولوو FH500", "خودرو سنگین", "تهران", "شهرک صنعتی", 8750000000, "ولوو", "FH500", 1398, 520000, "گازوئیل", "اتوماتیک", "سفید", "D13", "بدون تصادف", "نمایشگاه", "machine"),
        ("کامیونت ایسوزو 6 تن", "خودرو سنگین", "مشهد", "طوس", 3300000000, "ایسوزو", "NPR75", 1400, 210000, "گازوئیل", "دستی", "سفید", "4HK1", "بدون تصادف", "شخصی", "machine"),
        ("خاور 608 مدل 1379", "خودرو سنگین", "اصفهان", "دولت‌آباد", 1750000000, "مرسدس", "608", 1379, 480000, "گازوئیل", "دستی", "آبی", "OM352", "بدون تصادف", "شخصی", "machine"),
        ("تریلی کفی سه محور", "خودرو سنگین", "تبریز", "جاده سنتو", 2450000000, "ماموت", "کفی", 1396, 0, "گازوئیل", "دستی", "قرمز", "کشنده", "بدون تصادف", "نمایشگاه", "machine"),
        ("اتوبوس شهری کارکرده", "خودرو سنگین", "شیراز", "بلوار مدرس", 4200000000, "اسکانیا", "شهری", 1395, 650000, "گازوئیل", "اتوماتیک", "سفید", "DC9", "بدون تصادف", "نمایشگاه", "machine"),

        ("بیل مکانیکی کوماتسو PC200", "ماشین‌آلات و تجهیزات", "تهران", "حسن‌آباد", 12600000000, "کوماتسو", "PC200", 1397, 7200, "گازوئیل", "هیدرواستاتیک", "زرد", "SAA6D107", "بدون تصادف", "نمایشگاه", "machine"),
        ("لودر ولوو L90", "ماشین‌آلات و تجهیزات", "مشهد", "شهرک صنعتی", 9800000000, "ولوو", "L90", 1396, 8300, "گازوئیل", "اتوماتیک", "زرد", "D6", "بدون تصادف", "شخصی", "machine"),
        ("لیفتراک 3 تن دوگانه‌سوز", "ماشین‌آلات و تجهیزات", "اصفهان", "شاهین‌شهر", 1850000000, "تويوتا", "3 تن", 1398, 4100, "دوگانه‌سوز", "اتوماتیک", "نارنجی", "4Y", "بدون تصادف", "نمایشگاه", "machine"),
        ("غلتک راه‌سازی 10 تن", "ماشین‌آلات و تجهیزات", "کرمان", "جاده ماهان", 3200000000, "هپکو", "10 تن", 1395, 5200, "گازوئیل", "هیدرواستاتیک", "زرد", "دیزل", "بدون تصادف", "نمایشگاه", "machine"),
        ("تراکتور کشاورزی فرگوسن", "ماشین‌آلات و تجهیزات", "ارومیه", "جاده سلماس", 2750000000, "فرگوسن", "285", 1399, 3600, "گازوئیل", "دستی", "قرمز", "4 سیلندر", "بدون تصادف", "شخصی", "machine"),

        ("قایق تفریحی فایبرگلاس 6 نفره", "قایق و وسایل دریایی", "بندرعباس", "ساحل سورو", 2950000000, "فایبرگلاس", "تفریحی", 1400, 0, "بنزین", "دستی", "سفید", "150HP", "بدون تصادف", "شخصی", "boat"),
        ("جت اسکی یاماها", "قایق و وسایل دریایی", "کیش", "مرکز جزیره", 2450000000, "یاماها", "WaveRunner", 1401, 0, "بنزین", "اتوماتیک", "آبی", "1800cc", "بدون تصادف", "نمایشگاه", "boat"),
        ("قایق ماهیگیری فایبرگلاس", "قایق و وسایل دریایی", "بوشهر", "بندرگاه", 1350000000, "فایبرگلاس", "ماهیگیری", 1398, 0, "بنزین", "دستی", "سفید", "115HP", "بدون تصادف", "شخصی", "boat"),
        ("موتور قایق سوزوکی 60 اسب", "قایق و وسایل دریایی", "انزلی", "بندر انزلی", 580000000, "سوزوکی", "60HP", 1400, 0, "بنزین", "دستی", "مشکی", "60HP", "بدون تصادف", "شخصی", "boat"),
        ("قایق کابین‌دار خانوادگی", "قایق و وسایل دریایی", "چابهار", "لیپار", 5200000000, "فایبرگلاس", "Cabin", 1399, 0, "بنزین", "اتوماتیک", "سفید", "250HP", "بدون تصادف", "نمایشگاه", "boat"),

        ("رینگ آلومینیومی اسپرت 17 اینچ", "قطعات و لوازم نقلیه", "تهران", "چراغی", 78000000, "BBS", "17", 1403, 0, "", "", "مشکی", "", "نو", "شخصی", "parts"),
        ("لاستیک چهار حلقه 205/55R16", "قطعات و لوازم نقلیه", "مشهد", "خیابان امام", 42000000, "هانکوک", "205/55R16", 1404, 0, "", "", "مشکی", "", "نو", "نمایشگاه", "parts"),
        ("موتور کامل پژو TU5", "قطعات و لوازم نقلیه", "اصفهان", "امیرکبیر", 185000000, "پژو", "TU5", 1401, 0, "", "", "نقره‌ای", "TU5", "سالم", "شخصی", "parts"),
        ("چراغ جلو دنا پلاس جفت", "قطعات و لوازم نقلیه", "شیراز", "بلوار امیرکبیر", 14500000, "دنا", "پلاس", 1403, 0, "", "", "شفاف", "", "نو", "نمایشگاه", "parts"),
        ("گیربکس اتوماتیک کیا سراتو", "قطعات و لوازم نقلیه", "کرج", "مهرشهر", 265000000, "کیا", "سراتو", 1398, 0, "", "اتوماتیک", "نقره‌ای", "", "سالم", "شخصی", "parts"),
    ]

    image_map = DEMO_VEHICLE_IMAGES
    created = []
    for row in rows:
        title, category, city, district, price, brand, model, year, mileage, fuel, gearbox, color, engine, accident, seller, image_key = row
        image = image_map[image_key]
        created.append(VehicleAdModel(
            user_id=owner.id, title=title, category=category, city=city, district=district,
            price=price, negotiable=True, description=f"آگهی نمونه خریدینو برای نمایش امکانات بازارچه. وضعیت: {accident}. برای اطلاعات بیشتر با آگهی‌دهنده تماس بگیرید.",
            phone="09120000000", brand=brand, model=model, year=year, mileage=mileage, fuel=fuel,
            gearbox=gearbox, body_color=color, engine=engine, accident_status=accident,
            seller_type=seller, image=image, gallery=image, status="approved"
        ))
    db.session.add_all(created)
    db.session.commit()
    return len(created)
