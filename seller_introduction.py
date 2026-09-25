"""Public seller acquisition landing page for Kharidino."""
from flask import render_template

from app import app, db, Store, Product, Offer, Review
from merchant_marketplace import MerchantStore, SellerProduct


@app.route("/seller-introduction")
def seller_introduction():
    """Show the seller benefits and onboarding flow using live marketplace metrics."""
    try:
        active_stores = Store.query.filter_by(active=True).count()
        active_products = Product.query.filter_by(active=True).count()
        active_offers = Offer.query.filter_by(in_stock=True).count()
        seller_count = MerchantStore.query.filter_by(status="approved").count()
        seller_products = SellerProduct.query.count()
        review_count = Review.query.count()
    except Exception:
        active_stores = active_products = active_offers = seller_count = seller_products = review_count = 0

    return render_template(
        "seller_introduction.html",
        seller_metrics={
            "stores": active_stores,
            "products": max(active_products, seller_products),
            "offers": active_offers,
            "sellers": seller_count,
            "reviews": review_count,
        },
    )
