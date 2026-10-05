"""Security and smoke coverage for the Kharidino Gaming module."""
from __future__ import annotations

import os

os.environ["PAYMENT_PROVIDER"] = "disabled"
os.environ["PAYMENT_TEST_MODE"] = "1"

from app import app, db


GET_ROUTES = [
    "/gaming",
    "/gaming/club",
    "/gaming/party",
    "/gaming/teams",
    "/gaming/matchmaking",
    "/gaming/tournaments",
    "/gaming/leaderboard",
    "/gaming/arena",
    "/gaming/quests",
    "/gaming/store",
]

POST_ROUTES = [
    "/gaming/profile/setup",
    "/gaming/follow/1",
    "/gaming/friend/1",
    "/gaming/team/create",
    "/gaming/team/1/join",
    "/gaming/post/create",
    "/gaming/post/1/like",
    "/gaming/post/1/comment",
    "/gaming/matchmaking/create",
    "/gaming/tournament/1/join",
    "/gaming/party/create",
    "/gaming/party/1/join",
    "/gaming/platform/connect",
    "/gaming/clip/create",
    "/gaming/report",
    "/gaming/quests/1/claim",
    "/gaming/seller/profile",
    "/gaming/store/create",
    "/gaming/store/1/status",
    "/admin/gaming/1",
    "/admin/gaming-control/listing/1",
]


def test_gaming_public_pages_smoke():
    app.config.update(TESTING=True)
    client = app.test_client()
    for path in GET_ROUTES:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)


def test_gaming_state_changes_require_csrf():
    app.config.update(TESTING=True)
    client = app.test_client()
    for path in POST_ROUTES:
        response = client.post(path, data={}, headers={"Origin": "http://localhost"})
        assert response.status_code == 403, (path, response.status_code)


def test_gaming_post_forms_expose_runtime_csrf_token():
    app.config.update(TESTING=True)
    client = app.test_client()
    for path in ("/gaming/club", "/gaming/party", "/gaming/teams", "/gaming/matchmaking",
                 "/gaming/tournaments", "/gaming/quests"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        if "<form" in body and "method=\"post\"" in body.lower():
            assert 'name="csrf_token"' in body
