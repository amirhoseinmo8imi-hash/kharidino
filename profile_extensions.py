import os
import uuid
from flask import request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from app import app, db, User, login_required


class UserProfile(db.Model):
    __tablename__ = "kharidino_user_profile"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    first_name = db.Column(db.String(100), default="")
    last_name = db.Column(db.String(100), default="")
    display_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(30), default="")
    birth_date = db.Column(db.String(20), default="")
    gender = db.Column(db.String(30), default="")
    province = db.Column(db.String(100), default="")
    city = db.Column(db.String(100), default="")
    postal_code = db.Column(db.String(20), default="")
    address = db.Column(db.Text, default="")
    bio = db.Column(db.Text, default="")
    avatar = db.Column(db.String(500), default="")
    user = db.relationship("User", backref=db.backref("profile", uselist=False, cascade="all, delete-orphan"))


def get_current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def get_or_create_profile(user):
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if profile is None:
        profile = UserProfile(user_id=user.id, display_name=user.name or "")
        db.session.add(profile)
        db.session.commit()
    return profile


def profile_completion(profile):
    fields = [profile.first_name, profile.last_name, profile.phone, profile.birth_date,
              profile.gender, profile.province, profile.city, profile.postal_code,
              profile.address, profile.avatar]
    return round(sum(bool(str(value or "").strip()) for value in fields) / len(fields) * 100)


@app.context_processor
def inject_user_profile():
    user = get_current_user()
    if not user:
        return {"user_profile": None, "profile_completion_percent": 0}
    profile = get_or_create_profile(user)
    return {"user_profile": profile, "profile_completion_percent": profile_completion(profile)}


@app.post("/profile/update")
@login_required
def update_profile():
    user = get_current_user()
    profile = get_or_create_profile(user)
    fields = ["first_name", "last_name", "display_name", "phone", "birth_date", "gender",
              "province", "city", "postal_code", "address", "bio"]
    for field in fields:
        setattr(profile, field, request.form.get(field, "").strip())
    if profile.display_name:
        user.name = profile.display_name
    db.session.commit()
    flash("اطلاعات حساب با موفقیت ذخیره شد.", "success")
    return redirect(url_for("profile"))


@app.post("/profile/avatar")
@login_required
def update_avatar():
    user = get_current_user()
    profile = get_or_create_profile(user)
    upload = request.files.get("avatar")
    if not upload or not upload.filename:
        flash("یک تصویر برای پروفایل انتخاب کنید.", "error")
        return redirect(url_for("profile"))
    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        flash("فرمت تصویر مجاز نیست.", "error")
        return redirect(url_for("profile"))
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    if size > 5 * 1024 * 1024:
        flash("حجم عکس پروفایل باید حداکثر ۵ مگابایت باشد.", "error")
        return redirect(url_for("profile"))
    folder = os.path.abspath(os.path.join(app.static_folder, "uploads", "profiles"))
    os.makedirs(folder, exist_ok=True)
    filename = secure_filename(f"{uuid.uuid4().hex}{ext}")
    target = os.path.abspath(os.path.join(folder, filename))
    upload.save(target)
    if profile.avatar:
        old_path = os.path.abspath(os.path.join(app.static_folder, profile.avatar.lstrip("/")))
        try:
            if os.path.commonpath([old_path, folder]) == folder and os.path.isfile(old_path):
                os.remove(old_path)
        except ValueError:
            pass
    profile.avatar = f"uploads/profiles/{filename}"
    db.session.commit()
    flash("عکس پروفایل به‌روزرسانی شد.", "success")
    return redirect(url_for("profile"))


@app.post("/profile/avatar/remove")
@login_required
def remove_avatar():
    user = get_current_user()
    profile = get_or_create_profile(user)
    if profile.avatar:
        path = os.path.abspath(os.path.join(app.static_folder, profile.avatar.lstrip("/")))
        folder = os.path.abspath(os.path.join(app.static_folder, "uploads", "profiles"))
        try:
            if os.path.commonpath([path, folder]) == folder and os.path.isfile(path):
                os.remove(path)
        except ValueError:
            pass
    profile.avatar = ""
    db.session.commit()
    flash("عکس پروفایل حذف شد.", "success")
    return redirect(url_for("profile"))
