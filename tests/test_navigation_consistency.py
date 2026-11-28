from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_navigation_system_is_loaded_after_legacy_layers():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "kharidino-navigation-system.css" in base
    assert base.index("kharidino-navigation-system.css") > base.index("kharidino-unified-app-2026.css")


def test_grouped_category_taxonomy_is_exposed_globally():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert '"category_navigation_groups": category_navigation_groups' in app
    assert "category_navigation_groups" in base
    assert "data-mega-target=\"mega-panel-{{ cat.id }}\"" in base


def test_category_page_has_shared_category_navigation_and_clean_filter_markup():
    category = (ROOT / "templates" / "category.html").read_text(encoding="utf-8")
    assert "kh-category-quick-nav" in category
    assert "name=\"stock\"" in category
    assert "وضعیت کالا\\n" not in category


def test_category_stock_filter_is_applied_by_the_route():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    route = app[app.index("def category(category_id):"):app.index("# PRICE ALERT", app.index("def category(category_id):"))]
    assert 'request.args.get("stock"' in route
    assert 'stock_filter == "available"' in route
    assert 'stock_filter == "unavailable"' in route
    assert "stock=stock_filter" in route


def test_home_has_grouped_category_directory():
    home = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "kharidino-navigation-system.css").read_text(encoding="utf-8")
    assert "kh-home-category-directory" in home
    assert "category_navigation_groups" in home
    assert ".kh-home-category-groups" in css
