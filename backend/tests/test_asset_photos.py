"""Box / storage photos on an asset (CLOUDAPPG5-147, GitHub #98).

    POST /assets/photos/presign  ->  PUT the photo  ->  POST/PATCH /assets with
    location_image_key  ->  GET /assets/{id} carries location_image_url

Runs on the `local` storage backend, like test_documents.py.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.models.workspace import Workspace
from app.services import asset_photo, storage
from tests.test_asset_create import body


@pytest.fixture(autouse=True)
def uploads_in_tmp(tmp_path: Path):
    original = settings.local_upload_dir
    settings.local_upload_dir = str(tmp_path / "uploads")
    try:
        yield
    finally:
        settings.local_upload_dir = original


def _path_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def presign(api: TestClient, filename: str = "box.jpg", content_type: str = "image/jpeg") -> dict:
    response = api.post(
        "/assets/photos/presign", json={"filename": filename, "content_type": content_type}
    )
    assert response.status_code == 200, response.text
    return response.json()


def upload_photo(api: TestClient, data: bytes = b"jpeg-bytes") -> str:
    reserved = presign(api)
    response = api.put(
        _path_of(reserved["upload_url"]), content=data, headers={"Content-Type": "image/jpeg"}
    )
    assert response.status_code == 204, response.text
    return reserved["key"]


# --- presign -----------------------------------------------------------------


def test_presign_reserves_a_photo_key_in_this_workspace(api: TestClient, workspace: Workspace) -> None:
    reserved = presign(api, filename="กล่อง (1).jpg")

    key = reserved["key"]
    assert key.startswith("workspaces/")
    assert f"-{workspace.id}/users/" in key
    assert "/photos/" in key
    assert asset_photo.owns(workspace.id, key)
    assert "/assets/photos/dev-upload?" in reserved["upload_url"]


@pytest.mark.parametrize("content_type", ["application/pdf", "text/html", "image/svg+xml"])
def test_presign_takes_photos_only(api: TestClient, content_type: str) -> None:
    response = api.post(
        "/assets/photos/presign", json={"filename": "x", "content_type": content_type}
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "content_type"]


# --- save and show -------------------------------------------------------------


def test_a_saved_photo_shows_on_the_asset(api: TestClient) -> None:
    key = upload_photo(api, b"the-box-photo")

    created = api.post("/assets", json=body(location_image_key=key))

    assert created.status_code == 201, created.text
    url = created.json()["location_image_url"]
    assert "/assets/photos/dev-view?" in url
    # An <img> sends no auth headers; the signed link is enough.
    shown = TestClient(app).get(_path_of(url))
    assert shown.status_code == 200
    assert shown.content == b"the-box-photo"
    assert shown.headers["content-type"] == "image/jpeg"

    again = api.get(f"/assets/{created.json()['id']}").json()
    assert again["location_image_url"] is not None


def test_no_photo_means_no_url(api: TestClient) -> None:
    created = api.post("/assets", json=body()).json()
    assert created["location_image_url"] is None


def test_patch_replaces_and_removes_the_photo(api: TestClient) -> None:
    created = api.post("/assets", json=body(location_image_key=upload_photo(api))).json()

    replaced = api.patch(
        f"/assets/{created['id']}", json={"location_image_key": upload_photo(api, b"new")}
    )
    assert replaced.status_code == 200
    assert TestClient(app).get(_path_of(replaced.json()["location_image_url"])).content == b"new"

    removed = api.patch(f"/assets/{created['id']}", json={"location_image_key": None})
    assert removed.status_code == 200
    assert removed.json()["location_image_url"] is None


# --- keys an asset may not point at ------------------------------------------


def _bad_keys(workspace: Workspace, other_workspace: Workspace) -> list[str]:
    ours = f"workspaces/acme-{workspace.id}/users/me-{uuid.uuid4()}"
    return [
        # Another workspace's photo.
        f"workspaces/them-{other_workspace.id}/users/x-{uuid.uuid4()}/photos/a.jpg",
        # A receipt in our own workspace: no photos/ folder.
        f"{ours}/{uuid.uuid4()}-receipt.jpg",
        # Made-up shapes.
        "somewhere/else.jpg",
        f"{ours}/photos/../../../etc/passwd",
        f"{ours}/photos/",
    ]


def test_create_rejects_keys_that_are_not_this_workspaces_photos(
    api: TestClient, workspace: Workspace, other_workspace: Workspace
) -> None:
    for key in _bad_keys(workspace, other_workspace):
        response = api.post("/assets", json=body(location_image_key=key))
        assert response.status_code == 422, key
        assert response.json()["detail"][0]["loc"] == ["body", "location_image_key"]


def test_patch_rejects_them_too(
    api: TestClient, workspace: Workspace, other_workspace: Workspace
) -> None:
    created = api.post("/assets", json=body()).json()
    for key in _bad_keys(workspace, other_workspace):
        response = api.patch(f"/assets/{created['id']}", json={"location_image_key": key})
        assert response.status_code == 422, key


# --- the dev-only routes -------------------------------------------------------


def test_dev_upload_refuses_another_workspaces_key(api: TestClient, other_workspace: Workspace) -> None:
    key = f"workspaces/them-{other_workspace.id}/users/x-{uuid.uuid4()}/photos/a.jpg"
    response = api.put("/assets/photos/dev-upload", params={"key": key}, content=b"x")
    assert response.status_code == 404


def test_a_tampered_or_expired_photo_link_is_refused(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = api.post("/assets", json=body(location_image_key=upload_photo(api))).json()
    url = _path_of(created["location_image_url"])
    anonymous = TestClient(app)

    assert anonymous.get(url.replace("signature=", "signature=0")).status_code == 403

    # A valid signature for one key does not open another.
    query = parse_qs(urlsplit(url).query)
    other = query["key"][0].replace("/photos/", "/photos/x")
    assert anonymous.get(
        "/assets/photos/dev-view",
        params={"key": other, "expires": query["expires"][0], "signature": query["signature"][0]},
    ).status_code == 403

    later = time.time() + settings.presigned_url_ttl_seconds + 1
    monkeypatch.setattr(time, "time", lambda: later)
    assert anonymous.get(url).status_code == 403


def test_dev_routes_are_off_on_s3(api: TestClient, monkeypatch: pytest.MonkeyPatch, workspace: Workspace) -> None:
    key = f"workspaces/acme-{workspace.id}/users/me-{uuid.uuid4()}/photos/a.jpg"
    monkeypatch.setattr(settings, "storage_backend", "s3")
    assert api.put("/assets/photos/dev-upload", params={"key": key}, content=b"x").status_code == 404
    assert TestClient(app).get(
        "/assets/photos/dev-view", params={"key": key, "expires": 9999999999, "signature": "x"}
    ).status_code == 404


def test_on_s3_the_upload_and_view_are_presigned(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeS3:
        def generate_presigned_url(self, operation: str, Params: dict, ExpiresIn: int) -> str:
            calls.append((operation, Params))
            return f"https://bucket.example/{operation}"

    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_bucket_name", "bucket")
    monkeypatch.setattr(storage, "_client", lambda: FakeS3())

    reserved = presign(api, content_type="image/png")
    assert reserved["upload_url"] == "https://bucket.example/put_object"
    assert calls[0][1]["ContentType"] == "image/png"

    created = api.post("/assets", json=body(location_image_key=reserved["key"])).json()
    assert created["location_image_url"] == "https://bucket.example/get_object"
