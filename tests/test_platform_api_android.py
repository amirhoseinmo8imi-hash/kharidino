from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_versioned_platform_api_exposes_market_explore_and_cinema():
    source = (ROOT / "platform_api.py").read_text(encoding="utf-8")
    assert '"/api/v1/market/products"' in source
    assert '"/api/v1/market/products/<int:product_id>/offers"' in source
    assert '"/api/v1/explore/feed"' in source
    assert '"/api/v1/cinema/titles"' in source
    assert '"/api/v1/platform"' in source


def test_android_project_has_native_compose_shell_and_retrofit_contracts():
    root = ROOT / "android"
    assert (root / "settings.gradle.kts").exists()
    assert (root / "app" / "src" / "main" / "AndroidManifest.xml").exists()
    activity = (root / "app" / "src" / "main" / "java" / "ir" / "kharidino" / "app" / "MainActivity.kt").read_text(encoding="utf-8")
    api = (root / "app" / "src" / "main" / "java" / "ir" / "kharidino" / "app" / "PlatformApi.kt").read_text(encoding="utf-8")
    assert "NavigationBar" in activity
    assert "PlatformApi.create()" in activity
    assert 'api/v1/explore/feed' in api
    assert 'api/v1/cinema/titles' in api
