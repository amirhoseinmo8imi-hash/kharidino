"""Public storefront for approved Kharidino sellers."""
from flask import abort, render_template

from app import app, db, Store, Offer
from merchant_marketplace import MerchantStore, SellerProduct


@app.get("/stores/<int:store_id>")
def storefront(store_id):
    store = db.session.get(Store, store_id)
    if not store or not store.active:
        abort(404)
    account = MerchantStore.query.filter_by(store_id=store.id, status="approved").first()
    if not account:
        abort(404)

    links = SellerProduct.query.filter_by(store_id=store.id).order_by(SellerProduct.id.desc()).all()
    products = [link.product for link in links if link.product and link.product.active]
    offers = Offer.query.filter_by(store_id=store.id).all()
    offers_by_product = {offer.product_id: offer for offer in offers}
    ratings = [int(review.rating or 0) for product in products for review in product.reviews]
    rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

    try:
        from merchant_marketplace_v2 import SellerOrder
        seller_orders = SellerOrder.query.filter_by(store_id=store.id).all()
        delivered = sum(1 for order in seller_orders if order.status == "delivered")
    except Exception:
        delivered = 0

    stats = {"rating": rating, "reviews": len(ratings), "delivered": delivered}
    return render_template(
        "storefront.html",
        store=store,
        products=products,
        offers=offers,
        offers_by_product=offers_by_product,
        stats=stats,
    )
