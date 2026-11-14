"""Photos of an asset's box or where it is kept (CLOUDAPPG5-147, GitHub #98).

Same shape as receipts, without a database row: the browser asks for an
upload URL, PUTs the photo straight to the private bucket, then saves the
asset with the returned key in `location_image_key`. Viewing uses a
short-lived presigned GET, put on the asset detail as `location_image_url`.

No row is needed because the key itself says whose it is: photos live under
`workspaces/<name>-<workspace id>/users/<name>-<user id>/photos/`. `owns()`
checks that shape before an asset may point at a key, so an asset can neither
borrow another workspace's photo nor point at a receipt, whose keys have no
`photos/` folder. Without that check an employee could set a colleague's
receipt as a box photo and read it through `location_image_url`, which the
receipt routes deliberately refuse (CLOUDAPPG5-96).
"""

from __future__ import annotations

import mimetypes
import uuid
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.workspace import Workspace
from app.services import storage

#: The folder that marks a key as an asset photo.
PHOTO_FOLDER = "photos"

#: What a phone camera or a photo library hands the browser. HEIC is what an
#: iPhone saves by default.
ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
)


class NotAPhoto(ValueError):
    """The upload is not one of ALLOWED_CONTENT_TYPES."""


def reserve(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content_type: str,
) -> tuple[str, str]:
    """A fresh key for one photo and the URL to PUT it to."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise NotAPhoto(content_type)

    workspace = db.get(Workspace, workspace_id)
    uploader = db.get(User, user_id)
    key = storage.object_key(
        workspace_id,
        filename,
        workspace_name=workspace.name if workspace else None,
        uploader_id=user_id,
        uploader_name=uploader.display_name if uploader else None,
        folder=PHOTO_FOLDER,
    )

    presigned = storage.presigned_put_url(key, content_type)
    if presigned is not None:
        return key, presigned
    query = urlencode({"key": key})
    return key, f"{settings.api_base_url.rstrip('/')}/assets/photos/dev-upload?{query}"


def owns(workspace_id: uuid.UUID, key: str) -> bool:
    """Whether `key` is an asset photo reserved in this workspace.

    `workspaces/<label>-<workspace id>/users/<label>-<user id>/photos/<file>`:
    exactly six segments, the workspace id at the end of the second, and
    `photos` in the fifth.
    """
    parts = key.split("/")
    return (
        len(parts) == 6
        and parts[0] == "workspaces"
        and parts[1].endswith(f"-{workspace_id}")
        and parts[2] == "users"
        and parts[4] == PHOTO_FOLDER
        and parts[5] not in {"", ".", ".."}
    )


def view_url(key: str | None) -> str | None:
    """A short-lived URL an `<img>` can load, or None when there is no photo.

    Signing is a local computation on both backends, so this costs no network
    call per asset. A storage failure hides the photo rather than failing the
    whole asset page.
    """
    if not key:
        return None
    try:
        presigned = storage.presigned_get_url(key)
    except storage.StorageError:
        return None
    if presigned is not None:
        return presigned

    expires = storage.dev_link_expiry()
    query = urlencode({
        "key": key,
        "expires": expires,
        "signature": storage.dev_link_signature(f"photo:{key}", expires),
    })
    return f"{settings.api_base_url.rstrip('/')}/assets/photos/dev-view?{query}"


def dev_view_allowed(key: str, expires: int, signature: str) -> bool:
    """Whether a local-backend photo link is genuine and still in date."""
    return storage.dev_link_valid(f"photo:{key}", expires, signature)


def content_type_of(key: str) -> str:
    """The type to serve a locally stored photo with, from its extension."""
    guessed, _ = mimetypes.guess_type(key)
    return guessed if guessed in ALLOWED_CONTENT_TYPES else "application/octet-stream"
