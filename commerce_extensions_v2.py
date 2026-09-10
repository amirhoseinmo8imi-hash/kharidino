"""Secure, isolated commerce extensions for Kharidino."""
from datetime import datetime
from decimal import Decimal
from flask import jsonify, flash, redirect, render_template, request, session, url_for, abort, has_request_context
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from app import app, db, User, Order, admin_required, login_required
from marketplace_ultimate import Coupon, CouponRedemption

class Address(db.Model):
    __tablename__ = "kharidino_address"
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True); title=db.Column(db.String(80),nullable=False,default="آدرس من"); recipient_name=db.Column(db.String(120),nullable=False); phone=db.Column(db.String(30),nullable=False); province=db.Column(db.String(100),nullable=False,default=""); city=db.Column(db.String(100),nullable=False,default=""); postal_code=db.Column(db.String(20),nullable=False,default=""); address=db.Column(db.Text,nullable=False); is_default=db.Column(db.Boolean,nullable=False,default=False); created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)

class OrderStatusHistory(db.Model):
    __tablename__="kharidino_order_status_history"
    id=db.Column(db.Integer,primary_key=True); order_id=db.Column(db.Integer,db.ForeignKey("order.id"),nullable=False,index=True); old_status=db.Column(db.String(30)); new_status=db.Column(db.String(30),nullable=False); actor_user_id=db.Column(db.Integer,db.ForeignKey("user.id")); note=db.Column(db.String(300),default=""); created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow); order=db.relationship("Order",backref=db.backref("status_history",lazy=True,cascade="all, delete-orphan"))

class Notification(db.Model):
    __tablename__="kharidino_notification"
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True); title=db.Column(db.String(160),nullable=False); body=db.Column(db.Text,default=""); kind=db.Column(db.String(40),default="system"); is_read=db.Column(db.Boolean,nullable=False,default=False); created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow); user=db.relationship("User",backref=db.backref("notifications",lazy=True,cascade="all, delete-orphan"))

def _user():
    uid=session.get("user_id"); return db.session.get(User,uid) if uid else None

def _owned_order(order_id):
    user=_user(); order=db.session.get(Order,order_id) if user else None
    return order if order and (user.role=="admin" or order.user_id==user.id) else None

def _discount(coupon,total):
    if not coupon or not coupon.active or total<coupon.min_order or (coupon.expires_at and coupon.expires_at<datetime.utcnow()) or (coupon.usage_limit is not None and coupon.used_count>=coupon.usage_limit): return 0
    if coupon.kind=="fixed": return min(int(coupon.value),int(total))
    discount=min(int(total),int(Decimal(total)*Decimal(coupon.value)/Decimal(100)))
    if coupon.max_discount is not None: discount=min(discount,max(0,int(coupon.max_discount)))
    return discount

@app.route("/account/addresses",methods=["GET","POST"])
@login_required
def account_addresses():
    user=_user()
    if request.method=="POST":
        data={k:(request.form.get(k) or "").strip() for k in ("title","recipient_name","phone","province","city","postal_code","address")}
        if not data["recipient_name"] or not data["phone"] or not data["city"] or not data["address"]: flash("نام گیرنده، تلفن، شهر و آدرس الزامی است.","danger"); return redirect(url_for("account_addresses"))
        first=Address.query.filter_by(user_id=user.id).first() is None; db.session.add(Address(user_id=user.id,is_default=first,**data)); db.session.commit(); flash("آدرس ذخیره شد.","success"); return redirect(url_for("account_addresses"))
    return render_template("account_addresses.html",addresses=Address.query.filter_by(user_id=user.id).order_by(Address.is_default.desc(),Address.id.desc()).all())

@app.post("/account/addresses/<int:address_id>/default")
@login_required
def set_default_address(address_id):
    user=_user(); row=db.session.get(Address,address_id)
    if not row or row.user_id!=user.id:return ("Not Found",404)
    Address.query.filter_by(user_id=user.id).update({Address.is_default:False}); row.is_default=True; db.session.commit(); return redirect(url_for("account_addresses"))

@app.post("/account/addresses/<int:address_id>/delete")
@login_required
def delete_address(address_id):
    user=_user(); row=db.session.get(Address,address_id)
    if not row or row.user_id!=user.id:return ("Not Found",404)
    was_default=row.is_default; db.session.delete(row); db.session.flush()
    if was_default:
        replacement=Address.query.filter_by(user_id=user.id).order_by(Address.id.desc()).first()
        if replacement:replacement.is_default=True
    db.session.commit(); return redirect(url_for("account_addresses"))

@app.get("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order=_owned_order(order_id)
    if not order:return ("Not Found",404)
    return render_template("order_detail.html",order=order)

@app.get("/api/orders/<int:order_id>")
@login_required
def order_detail_api(order_id):
    order=_owned_order(order_id)
    if not order:return jsonify({"error":"not_found"}),404
    return jsonify({"id":order.id,"status":order.status,"total":order.total,"created_at":order.created_at.isoformat() if order.created_at else None,"customer":{"name":order.customer_name,"phone":order.phone,"address":order.address},"items":[{"product_id":i.product_id,"name":i.product_name,"price":i.price,"quantity":i.quantity} for i in order.items],"history":[{"old_status":h.old_status,"new_status":h.new_status,"note":h.note,"created_at":h.created_at.isoformat()} for h in order.status_history]})

@app.post("/coupon/apply")
@login_required
def apply_coupon():
    code=(request.form.get("code") or "").strip().upper()[:80]; coupon=Coupon.query.filter_by(code=code).first()
    if not coupon:session.pop("coupon_code",None);return jsonify({"ok":False,"error":"کد تخفیف معتبر نیست."}),400
    from app import cart_data
    _,total=cart_data(); discount=_discount(coupon,total)
    if discount<=0:return jsonify({"ok":False,"error":"این کد برای سبد فعلی قابل استفاده نیست."}),400
    session["coupon_code"]=coupon.code; return jsonify({"ok":True,"code":coupon.code,"discount":discount,"total_after_discount":total-discount})

@app.post("/coupon/remove")
@login_required
def remove_coupon():
    session.pop("coupon_code",None); return jsonify({"ok":True})

@app.get("/account/notifications")
@login_required
def notifications():
    user=_user(); rows=Notification.query.filter_by(user_id=user.id).order_by(Notification.id.desc()).limit(100).all(); return render_template("notifications.html",notifications=rows)

@app.post("/account/notifications/<int:notification_id>/read")
@login_required
def notification_read(notification_id):
    user=_user(); row=db.session.get(Notification,notification_id)
    if not row or row.user_id!=user.id:return ("Not Found",404)
    row.is_read=True;db.session.commit();return redirect(url_for("notifications"))

@app.route("/admin/coupons",methods=["GET","POST"])
@admin_required
def admin_coupons():
    if request.method=="POST":
        code=(request.form.get("code") or "").strip().upper()[:80]; kind=request.form.get("kind") if request.form.get("kind") in {"percent","fixed"} else "percent"
        try:value=int(request.form.get("value","0")); min_order=max(0,int(request.form.get("min_total",request.form.get("min_order","0")))); usage_limit=int(request.form["max_uses"]) if request.form.get("max_uses") else (int(request.form["usage_limit"]) if request.form.get("usage_limit") else None)
        except ValueError:flash("مقادیر عددی نامعتبر است.","danger");return redirect(url_for("admin_coupons"))
        if not code or value<=0 or (kind=="percent" and value>100) or (usage_limit is not None and usage_limit<=0) or Coupon.query.filter_by(code=code).first():flash("اطلاعات کد تخفیف نامعتبر یا تکراری است.","danger");return redirect(url_for("admin_coupons"))
        db.session.add(Coupon(code=code,kind=kind,value=value,min_order=min_order,usage_limit=usage_limit));db.session.commit();flash("کد تخفیف ایجاد شد.","success");return redirect(url_for("admin_coupons"))
    return render_template("admin_coupons.html",coupons=Coupon.query.order_by(Coupon.id.desc()).all())

@app.post("/admin/coupons/<int:coupon_id>/toggle")
@admin_required
def toggle_coupon(coupon_id):
    row=db.session.get(Coupon,coupon_id)
    if not row:return ("Not Found",404)
    row.active=not row.active;db.session.commit();return redirect(url_for("admin_coupons"))

@event.listens_for(Session,"after_flush")
def _commerce_after_flush(session_obj,flush_context):
    actor=session.get("user_id") if has_request_context() else None
    for obj in list(session_obj.new)+list(session_obj.dirty):
        if not isinstance(obj,Order):continue
        state=inspect(obj);hist=state.attrs.status.history
        if obj in session_obj.new:
            session_obj.add(OrderStatusHistory(order=obj,old_status=None,new_status=obj.status,actor_user_id=actor or None))
            code=(session.get("coupon_code") or "").strip().upper() if has_request_context() else ""
            if code:
                coupon=Coupon.query.filter_by(code=code).first();discount=_discount(coupon,obj.total)
                if discount>0:
                    obj.total-=discount;coupon.used_count+=1;session_obj.add(CouponRedemption(coupon_id=coupon.id,user_id=obj.user_id,order_id=obj.id,discount=discount))
                session.pop("coupon_code",None)
        elif hist.has_changes():
            old=hist.deleted[0] if hist.deleted else None;new=hist.added[0] if hist.added else obj.status;session_obj.add(OrderStatusHistory(order=obj,old_status=old,new_status=new,actor_user_id=actor or None))

def apply_commerce_extensions(flask_app):
    flask_app.jinja_env.globals["unread_notification_count"]=lambda:Notification.query.filter_by(user_id=session.get("user_id"),is_read=False).count() if session.get("user_id") else 0
