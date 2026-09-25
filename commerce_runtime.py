"""Runtime bridges for the commerce extensions."""
from werkzeug.datastructures import MultiDict
from flask import request, session
from app import app
from commerce_extensions_v2 import Address

@app.post("/account/addresses/<int:address_id>/use")
def use_saved_address(address_id):
    from commerce_extensions_v2 import _user
    from app import db
    user = _user()
    if not user:
        return ("Not Found", 404)
    row = db.session.get(Address, address_id)
    if not row or row.user_id != user.id:
        return ("Not Found", 404)
    session["checkout_address_id"] = row.id
    return ("", 204)

@app.before_request
def _bridge_checkout_address():
    if request.endpoint != "checkout" or request.method != "POST":
        return None
    address_id = session.get("checkout_address_id")
    if not address_id:
        return None
    from commerce_extensions_v2 import _user
    from app import db
    user = _user()
    row = db.session.get(Address, address_id) if user else None
    if not row or row.user_id != user.id:
        session.pop("checkout_address_id", None)
        return None
    form = MultiDict(request.form)
    form["customer_name"] = row.recipient_name
    form["phone"] = row.phone
    form["address"] = ", ".join(x for x in (row.province, row.city, row.postal_code, row.address) if x)
    request.__dict__["form"] = form
    session.pop("checkout_address_id", None)
    return None
