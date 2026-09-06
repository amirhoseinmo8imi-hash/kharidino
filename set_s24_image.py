from app import app, db, Product

with app.app_context():
    product = Product.query.filter_by(name="Galaxy S24").first()

    if product:
        product.image = "uploads/products/galaxy-s24.jpg"
        db.session.commit()

        print("==============================================")
        print("✅ تصویر Galaxy S24 با موفقیت وصل شد")
        print("📷", product.image)
        print("==============================================")
    else:
        print("❌ محصول Galaxy S24 پیدا نشد.")