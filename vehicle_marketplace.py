from datetime import datetime
from flask import abort, flash, redirect, render_template, request, session, url_for
from pathlib import Path
import uuid
from werkzeug.utils import secure_filename

VEHICLE_CATEGORIES = [
    "خودرو سواری",
    "موتورسیکلت",
    "خودرو سنگین",
    "ماشین‌آلات و تجهیزات",
    "قایق و وسایل دریایی",
    "قطعات و لوازم نقلیه",
    "خودرو اقتصادی",
    "خودرو لوکس",
    "خودرو کلاسیک",
    "دوچرخه و اسکوتر",
]
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
    """Seed a rich demo classifieds catalog: about 50 ads per category.
    The records are synthetic examples inspired by common classifieds categories;
    they do not copy individual third-party listings.
    """
    if VehicleAdModel is None:
        return 0

    owner = User.query.filter_by(role="admin").order_by(User.id.asc()).first()
    if not owner:
        owner = User.query.order_by(User.id.asc()).first()
    if not owner:
        return 0

    # Keep existing real/demo ads and top each category up to 50.
    cities = [
        ("تهران","سعادت‌آباد"),("تهران","تهرانپارس"),("مشهد","احمدآباد"),
        ("اصفهان","مرداویج"),("شیراز","معالی‌آباد"),("تبریز","ولیعصر"),
        ("کرج","گوهردشت"),("رشت","گلسار"),("اهواز","کیانپارس"),("قم","صفائیه"),
        ("کرمان","جاده ماهان"),("ارومیه","جاده سلماس"),("بندرعباس","سورو"),
        ("بوشهر","بندرگاه"),("انزلی","بندر انزلی"),("چابهار","لیپار")
    ]

    catalog = {
        "خودرو سواری": [
            ("پژو","207",1180000000,"car"),("دنا","پلاس توربو",1045000000,"car2"),
            ("سمند","LX",690000000,"car3"),("هیوندای","النترا",2380000000,"car2"),
            ("کیا","سراتو",1560000000,"car3"),("تارا","V4",1450000000,"car"),
            ("شاهین","G",920000000,"car2"),("رانا","پلاس",760000000,"car3"),
            ("مزدا","3",1850000000,"car2"),("رنو","ساندرو",1250000000,"car"),
        ],
        "موتورسیکلت": [
            ("هوندا","125",185000000,"motorcycle"),("بنلی","249",420000000,"motorcycle"),
            ("باجاج","NS200",315000000,"motorcycle"),("کویر","150",145000000,"motorcycle"),
            ("وسپا","Primavera",610000000,"motorcycle"),("آپریلیا","SR",520000000,"motorcycle"),
            ("کاوازاکی","Ninja",1750000000,"motorcycle"),("یاماها","MT-15",760000000,"motorcycle"),
            ("TVS","Apache",410000000,"motorcycle"),("SYM","J200",390000000,"motorcycle"),
        ],
        "خودرو سنگین": [
            ("ولوو","FH500",8750000000,"machine"),("ایسوزو","NPR75",3300000000,"machine"),
            ("مرسدس","608",1750000000,"machine"),("ماموت","کفی سه محور",2450000000,"machine"),
            ("اسکانیا","اتوبوس شهری",4200000000,"machine"),("ولوو","FM",7200000000,"machine"),
            ("فوتون","کشنده",5400000000,"machine"),("دانگ فنگ","KX",6100000000,"machine"),
            ("بنز","2631",3900000000,"machine"),("ایویکو","Stralis",5800000000,"machine"),
        ],
        "ماشین‌آلات و تجهیزات": [
            ("کوماتسو","PC200",12600000000,"machine"),("ولوو","L90",9800000000,"machine"),
            ("تویوتا","لیفتراک 3 تن",1850000000,"machine"),("هپکو","غلتک 10 تن",3200000000,"machine"),
            ("فرگوسن","285",2750000000,"machine"),("کاترپیلار","320",14800000000,"machine"),
            ("کوماتسو","لودر WA200",8600000000,"machine"),("هیوندای","R210",10300000000,"machine"),
            ("بابکت","S650",5900000000,"machine"),("نیوهلند","تراکتور",3100000000,"machine"),
        ],
        "قایق و وسایل دریایی": [
            ("فایبرگلاس","تفریحی 6 نفره",2950000000,"boat"),("یاماها","WaveRunner",2450000000,"boat"),
            ("فایبرگلاس","ماهیگیری",1350000000,"boat"),("سوزوکی","موتور 60 اسب",580000000,"boat"),
            ("فایبرگلاس","Cabin",5200000000,"boat"),("مرکوری","موتور 90 اسب",920000000,"boat"),
            ("یاماها","قایق تفریحی",4100000000,"boat"),("فایبرگلاس","لانچ",2200000000,"boat"),
            ("Seadoo","Spark",2850000000,"boat"),("قایق‌سازی جنوب","ماهیگیری",1750000000,"boat"),
        ],
        "قطعات و لوازم نقلیه": [
            ("BBS","رینگ 17",78000000,"parts"),("هانکوک","205/55R16",42000000,"parts"),
            ("پژو","موتور TU5",185000000,"parts"),("دنا","چراغ جلو جفت",14500000,"parts"),
            ("کیا","گیربکس سراتو",265000000,"parts"),("سونی","سیستم صوتی خودرو",32000000,"parts"),
            ("بوش","دیسک و صفحه",28000000,"parts"),("MANN","فیلتر کامل",8500000,"parts"),
            ("پژو","ECU",46000000,"parts"),("کیا","آینه برقی",22000000,"parts"),
        ],
        "خودرو اقتصادی": [
            ("پراید","131",430000000,"car3"),("تیبا","2",510000000,"car"),
            ("ساینا","S",560000000,"car2"),("کوییک","S",620000000,"car3"),
            ("پژو","405",520000000,"car"),("پژو","206",610000000,"car2"),
            ("رانا","LX",690000000,"car3"),("سمند","EF7",650000000,"car"),
            ("شاهین","G",920000000,"car2"),("اطلس","G",780000000,"car3"),
        ],
        "خودرو لوکس": [
            ("مرسدس","E250",7800000000,"car2"),("BMW","530i",8200000000,"car"),
            ("لکسوس","ES250",6900000000,"car3"),("پورشه","Cayenne",14500000000,"car2"),
            ("آئودی","A6",7600000000,"car"),("ولوو","XC90",9300000000,"car3"),
            ("بنز","C200",6700000000,"car2"),("BMW","X3",8900000000,"car"),
            ("لکسوس","RX350",9800000000,"car3"),("مازراتی","Ghibli",12500000000,"car2"),
        ],
        "خودرو کلاسیک": [
            ("پیکان","جوانان",850000000,"car3"),("پیکان","استیشن",720000000,"car"),
            ("بنز","230E",2200000000,"car2"),("بنز","280",2600000000,"car3"),
            ("بیوک","Regal",1850000000,"car"),("کادیلاک","Seville",3100000000,"car2"),
            ("فولکس","Beetle",1450000000,"car3"),("مزدا","929",1200000000,"car"),
            ("تویوتا","Cressida",1700000000,"car2"),("رنو","5",680000000,"car3"),
        ],
        "دوچرخه و اسکوتر": [
            ("Giant","Talon",85000000,"parts"),("Scott","Aspect",120000000,"parts"),
            ("Merida","Big Nine",145000000,"parts"),("Trinx","M100",38000000,"parts"),
            ("Xiaomi","Electric Scooter",55000000,"parts"),("Ninebot","Max G2",95000000,"parts"),
            ("Cube","Aim",175000000,"parts"),("Btwin","Rockrider",72000000,"parts"),
            ("Phoenix","شهری",29000000,"parts"),("برقی","اسکوتر تاشو",68000000,"parts"),
        ],
    }

    image_map = DEMO_VEHICLE_IMAGES
    created = []
    for category, models in catalog.items():
        existing = VehicleAdModel.query.filter_by(category=category).count()
        needed = max(0, 50 - existing)
        for i in range(needed):
            brand, model, base_price, image_key = models[i % len(models)]
            city, district = cities[i % len(cities)]
            year = 1394 + (i % 11)
            mileage = 0 if category in {"قطعات و لوازم نقلیه","قایق و وسایل دریایی"} else 5000 + ((i * 731) % 180000)
            price = int(base_price * (0.88 + ((i % 9) * 0.035)))
            seller = "نمایشگاه" if i % 4 == 0 else "شخصی"
            gearbox = "اتوماتیک" if i % 3 == 0 else "دستی"
            fuel = "بنزین" if category not in {"خودرو سنگین","ماشین‌آلات و تجهیزات"} else "گازوئیل"
            title = f"{brand} {model} - آگهی شماره {i + existing + 1}"
            created.append(VehicleAdModel(
                user_id=owner.id,
                title=title,
                category=category,
                city=city,
                district=district,
                price=price,
                negotiable=(i % 2 == 0),
                description=f"آگهی نمونه خریدینو برای نمایش امکانات بازارچه. {brand} {model} در {city}؛ برای جزئیات و هماهنگی تماس بگیرید.",
                phone="09120000000",
                brand=brand,
                model=model,
                year=year,
                mileage=mileage,
                fuel=fuel,
                gearbox=gearbox,
                body_color=["سفید","مشکی","نقره‌ای","قرمز","آبی"][i % 5],
                engine="استاندارد",
                accident_status="بدون تصادف" if i % 5 else "یک لکه رنگ",
                seller_type=seller,
                image=image_map[image_key],
                gallery=image_map[image_key],
                status="approved",
            ))
    if created:
        db.session.add_all(created)
        db.session.commit()
    return len(created)
