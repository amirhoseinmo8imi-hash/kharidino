from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_store_map_has_public_directory_and_active_store_filter():
    source = (ROOT / "merchant_marketplace.py").read_text(encoding="utf-8")
    assert 'class StoreGeoLocation(db.Model):' in source
    assert '@app.get("/map")' in source
    assert '@app.get("/api/map/stores")' in source
    assert 'Store.active.is_(True)' in source
    assert 'StoreGeoLocation.latitude.isnot(None)' in source
    assert 'StoreGeoLocation.longitude.isnot(None)' in source


def test_seller_location_is_validated_and_kept_separate_from_profile_form():
    source = (ROOT / "merchant_marketplace.py").read_text(encoding="utf-8")
    start = source.index('def seller_store_save():')
    end = source.index('\n\n@app.post("/seller/product/save")', start)
    block = source[start:end]
    assert 'isfinite(latitude)' in block and 'isfinite(longitude)' in block
    assert '-90 <= latitude <= 90' in block
    assert '-180 <= longitude <= 180' in block
    assert 'any(key in request.form for key in ("address", "latitude", "longitude"))' in block


def test_store_map_page_uses_openstreetmap_and_has_mobile_layout():
    template = (ROOT / "templates" / "store_map.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "kharidino-store-map.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "kharidino-store-map.css").read_text(encoding="utf-8")
    assert "openstreetmap.org" in template
    assert "/api/map/stores" in script
    assert "navigator.geolocation" in script
    assert "@media(max-width:850px)" in css
