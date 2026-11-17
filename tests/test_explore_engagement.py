from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_explore_has_comments_saves_and_saved_collection():
    source = (ROOT / "explore.py").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "explore" / "index.html").read_text(encoding="utf-8")
    assert "class ExploreComment" in source
    assert "class ExploreSave" in source
    assert 'endpoint="explore_comment"' in source
    assert 'endpoint="explore_save"' in source
    assert 'endpoint="explore_saved"' in source
    assert "ExploreSave.user_id == session[\"user_id\"]" in source
    assert "url_for('explore_comment'" in template
    assert "url_for('explore_save'" in template
    assert "url_for('explore_saved'" in template


def test_explore_comments_validate_length_and_require_published_posts():
    source = (ROOT / "explore.py").read_text(encoding="utf-8")
    assert "if not post or post.status != \"published\":" in source
    assert "len(body) > 1000" in source
    assert "nullable=False, index=True" in source
