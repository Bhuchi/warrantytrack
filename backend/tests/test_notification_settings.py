"""GET / PUT /me/notification-settings and the In-app switch (GitHub #82)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.models.workspace import Workspace

URL = "/me/notification-settings"
DEFAULTS = {"in_app_enabled": True, "email_enabled": True, "remind_days": [30, 14, 7]}


def test_defaults_before_anything_is_saved(api: TestClient) -> None:
    response = api.get(URL)
    assert response.status_code == 200
    assert response.json() == DEFAULTS


def test_save_then_read_back_largest_first(api: TestClient) -> None:
    body = {"in_app_enabled": True, "email_enabled": False, "remind_days": [7, 30]}

    saved = api.put(URL, json=body)
    assert saved.status_code == 200
    assert saved.json() == {"in_app_enabled": True, "email_enabled": False, "remind_days": [30, 7]}
    assert api.get(URL).json() == saved.json()


def test_saving_again_replaces_the_settings(api: TestClient) -> None:
    api.put(URL, json={"in_app_enabled": False, "email_enabled": False, "remind_days": [60]})
    api.put(URL, json=DEFAULTS)
    assert api.get(URL).json() == DEFAULTS


def test_no_reminder_days_is_allowed(api: TestClient) -> None:
    response = api.put(URL, json={"in_app_enabled": True, "email_enabled": True, "remind_days": []})
    assert response.status_code == 200
    assert response.json()["remind_days"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"in_app_enabled": True, "email_enabled": True, "remind_days": [5]},       # not a chip
        {"in_app_enabled": True, "email_enabled": True, "remind_days": [30, 30]},  # duplicate
        {"in_app_enabled": True, "email_enabled": True, "remind_days": [0]},
        {"in_app_enabled": True, "email_enabled": True},                           # field missing
        {"in_app_enabled": True, "email_enabled": True, "remind_days": [30], "weekly_digest": True},
    ],
)
def test_bad_settings_are_422(api: TestClient, body: dict) -> None:
    assert api.put(URL, json=body).status_code == 422
    assert api.get(URL).json() == DEFAULTS


def test_signed_out_is_401(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.put(URL, json=DEFAULTS).status_code == 401


def test_in_app_off_hides_warranty_alerts_from_the_bell(
    api: TestClient, db: Session, workspace: Workspace, user: User
) -> None:
    for kind, title in [
        (NotificationType.warranty_expiring, "Laptop warranty expires in 7 days"),
        (NotificationType.warranty_expired, "Monitor warranty expired yesterday"),
        (NotificationType.asset_assigned, "Phone was assigned to you"),
    ]:
        db.add(Notification(workspace_id=workspace.id, user_id=user.id, type=kind, title=title))
    db.flush()

    assert api.get("/notifications").json()["unread"] == 3

    api.put(URL, json={**DEFAULTS, "in_app_enabled": False})
    bell = api.get("/notifications").json()

    assert bell["unread"] == 1
    assert [item["title"] for item in bell["items"]] == ["Phone was assigned to you"]
