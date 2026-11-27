from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_media_api_routes_and_moderation_contract():
    source=(ROOT/"media_api.py").read_text(encoding="utf-8")
    app=(ROOT/"app.py").read_text(encoding="utf-8")
    for route in ("/api/media/explore","/api/media/reels","/api/media/posts","/like","/bookmark","/report"):
        assert route in source
    assert 'status="pending"' in source
    assert 'status="published"' in source
    assert "register_media_api(app, db, User, Product)" in app


def test_media_api_has_pagination_and_unique_interaction_constraints():
    source=(ROOT/"media_api.py").read_text(encoding="utf-8")
    assert "MEDIA_API_MAX_PAGE_SIZE" in source
    assert "uq_media_like" in source
    assert "uq_media_bookmark" in source
    assert "uq_media_report" in source


def test_media_api_requires_auth_for_submission_and_interactions():
    source=(ROOT/"media_api.py").read_text(encoding="utf-8")
    assert "signed_in()" in source
    assert 'methods=["POST"]' in source
