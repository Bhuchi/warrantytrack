"""Object storage for uploaded receipts (CLOUDAPPG5-95).

The file never passes through this API in production. The browser is handed a
presigned URL and PUTs straight to a **private** S3 bucket; viewing later uses
a presigned GET with a short expiry. Nothing in the bucket is ever public, and
we store the object key rather than a URL — a stored URL would be expired by
the time anyone read it (docs/architecture.md, Decision 3).

Two backends, chosen by `STORAGE_BACKEND`:

* `s3` — the real thing.
* `local` — writes to a directory on the API container so the whole upload →
  OCR → confirm flow can be demoed with no AWS account. The browser PUTs to
  `/documents/{id}/dev-upload` instead of to S3; that route exists only on
  this backend and refuses to run in production.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class StorageError(RuntimeError):
    """The object store could not be reached, or is misconfigured."""


_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_DASHES = re.compile(r"-+")

# Built once and reused: creating a boto3 client parses config and costs real
# time, and a module-level client is safe to share across requests.
_s3_client = None


def _client():
    global _s3_client
    if _s3_client is None:
        if not settings.s3_bucket_name:
            raise StorageError(
                "STORAGE_BACKEND=s3 but S3_BUCKET_NAME is not set."
            )
        _s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            # A newly created Singapore bucket may redirect the global host.
            # Browsers cannot follow that redirect for a cross-origin PUT.
            endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        )
    return _s3_client


def safe_filename(filename: str) -> str:
    """A filename safe to put in an object key.

    Users upload `ใบเสร็จ (1).jpg` and `../../etc/passwd`. Keeping only
    `[A-Za-z0-9._-]` removes both problems — the path traversal and the
    characters that would need escaping in a URL. The original name is kept in
    `documents.filename`, so nothing is lost for display.
    """
    cleaned = _UNSAFE_FILENAME.sub("-", filename.strip()).strip("-.")
    return cleaned[:120] or "upload"


def safe_path_label(value: str | None, fallback: str) -> str:
    """Make a readable S3 prefix segment without allowing path syntax.

    Keep Unicode letters and marks so names in Thai and other scripts remain
    legible in the S3 console. Separators and punctuation become dashes; the
    caller adds an opaque ID suffix so duplicate names stay distinct.
    """
    normalized = unicodedata.normalize("NFKC", value or "").strip()
    if "@" in normalized:
        normalized = ""
    cleaned = "".join(
        char
        if unicodedata.category(char)[0] in {"L", "M", "N"} or char == "_"
        else "-"
        for char in normalized
    )
    cleaned = _REPEATED_DASHES.sub("-", cleaned).strip("-._")
    # Leave room for the separator and UUID suffix in a filesystem-safe
    # segment, including names that use multibyte Unicode characters.
    label: list[str] = []
    byte_length = 0
    for char in cleaned:
        char_length = len(char.encode("utf-8"))
        if len(label) >= 64 or byte_length + char_length > 200:
            break
        label.append(char)
        byte_length += char_length
    cleaned = "".join(label).rstrip("-._")
    return cleaned or fallback


def object_key(
    workspace_id: uuid.UUID,
    filename: str,
    *,
    workspace_name: str | None = None,
    uploader_id: uuid.UUID | None = None,
    uploader_name: str | None = None,
    folder: str | None = None,
) -> str:
    """Where one upload lives in the bucket.

    The workspace and uploader labels make S3 console folders understandable
    to an administrator. Stable UUID suffixes keep same-named workspaces and
    users distinct without placing email addresses in object keys. The random
    document segment keeps uploads of the same filename apart.
    """
    workspace_label = safe_path_label(workspace_name, "workspace")
    workspace_folder = f"{workspace_label}-{workspace_id}"

    if uploader_id is None:
        uploader_folder = "unknown-uploader"
    else:
        uploader_label = safe_path_label(uploader_name, "user")
        uploader_folder = f"{uploader_label}-{uploader_id}"

    # `folder` keeps kinds of upload apart, e.g. asset photos under
    # `photos/`, so a key of one kind can never be passed off as another.
    subfolder = f"{folder}/" if folder else ""
    return (
        f"workspaces/{workspace_folder}/users/{uploader_folder}/"
        f"{subfolder}{uuid.uuid4()}-{safe_filename(filename)}"
    )


def presigned_put_url(key: str, content_type: str | None) -> str | None:
    """A URL the browser may PUT this one object to, or None on `local`.

    Returning None rather than raising lets the caller fall back to the dev
    upload route without asking which backend is active.
    """
    if settings.storage_backend != "s3":
        return None
    params = {"Bucket": settings.s3_bucket_name, "Key": key}
    if content_type:
        # Signed into the URL, so the upload cannot claim a different type.
        params["ContentType"] = content_type
    try:
        return _client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=settings.presigned_url_ttl_seconds,
        )
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - needs AWS
        raise StorageError(f"Could not presign an upload for {key}: {exc}") from exc


def inline_disposition(filename: str | None) -> str | None:
    """`Content-Disposition: inline` that names the file as the user called it.

    `inline` so the browser shows a JPG, PNG or PDF instead of saving it, and
    the original name so "Save as" offers `ใบเสร็จ.jpg` rather than the object
    key. The plain `filename=` is an ASCII fallback with quotes and
    backslashes removed; `filename*=` (RFC 6266) carries the real name.
    """
    if not filename:
        return None
    fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in '"\\' else "_"
        for char in filename
    ).strip() or "download"
    return f"inline; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def presigned_get_url(
    key: str,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> str | None:
    """A short-lived URL for viewing one object, or None on `local`.

    `filename` and `content_type` are signed into the URL as response
    overrides, so S3 serves the file inline under its original name whatever
    metadata the upload left on the object.
    """
    if settings.storage_backend != "s3":
        return None
    params: dict[str, str] = {"Bucket": settings.s3_bucket_name, "Key": key}
    disposition = inline_disposition(filename)
    if disposition:
        params["ResponseContentDisposition"] = disposition
    if content_type:
        params["ResponseContentType"] = content_type
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=settings.presigned_url_ttl_seconds,
        )
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - needs AWS
        raise StorageError(f"Could not presign a download for {key}: {exc}") from exc


# --- local backend---------------------------------------------------------


def dev_link_signature(subject: str, expires: int) -> str:
    """Sign a local-backend link the way S3 signs a presigned one.

    A link opened in a new tab or an `<img>` carries no auth headers, so the
    dev-only routes that serve files trust this signature instead. `subject`
    names what the link opens, prefixed by kind (`document:<id>`,
    `photo:<key>`), so a signature for one thing never opens another.
    """
    message = f"dev-link:{subject}:{expires}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()


def dev_link_valid(subject: str, expires: int, signature: str) -> bool:
    """Whether a local-backend link is genuine and still in date."""
    if expires < time.time():
        return False
    return hmac.compare_digest(dev_link_signature(subject, expires), signature)


def dev_link_expiry() -> int:
    """When a local-backend link made now should stop working."""
    return int(time.time()) + settings.presigned_url_ttl_seconds


# --- local backend (files) ---------------------------------------------------------


def _local_path(key: str) -> Path:
    """Return a local path for a safe object key.

    Keep the key's folder structure so long workspace and uploader labels do
    not become one overlong filesystem component. Revalidate every segment
    here because this is where an object key becomes a filesystem path.
    """
    parts = key.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise StorageError(f"Refusing to write an unsafe key: {key!r}")

    for part in parts:
        if any(
            unicodedata.category(char)[0] not in {"L", "M", "N"}
            and char not in "._-"
            for char in part
        ):
            raise StorageError(f"Refusing to write an unsafe key: {key!r}")
        if len(part.encode("utf-8")) > 255:
            raise StorageError(f"Refusing to write an overlong key segment: {key!r}")

    root = Path(settings.local_upload_dir).resolve()
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root):
        raise StorageError(f"Refusing to write an unsafe key: {key!r}")
    return path


def write_local(key: str, data: bytes) -> None:
    """Store an upload on disk (`local` backend only)."""
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_bytes(key: str) -> bytes:
    """The stored object, from wherever this backend keeps it.

    OCR needs the bytes. Bedrock downloads the S3 object before sending it to
    the model; local development reads from disk.
    """
    if settings.storage_backend == "s3":
        try:
            return _client().get_object(
                Bucket=settings.s3_bucket_name, Key=key
            )["Body"].read()
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - needs AWS
            raise StorageError(f"Could not read {key}: {exc}") from exc

    path = _local_path(key)
    if not path.exists():
        raise StorageError(f"Nothing uploaded for {key} yet.")
    return path.read_bytes()


def exists(key: str) -> bool:
    """Whether the object has actually been uploaded.

    `POST /documents/{id}/submit` checks this before starting extraction, so a
    client that presigned and then never uploaded gets a clear error instead of
    a failed OCR job.
    """
    if settings.storage_backend == "s3":
        try:
            _client().head_object(Bucket=settings.s3_bucket_name, Key=key)
            return True
        except ClientError as exc:  # pragma: no cover - needs AWS
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageError(f"Could not check {key}: {exc}") from exc
        except BotoCoreError as exc:  # pragma: no cover - needs AWS
            raise StorageError(f"Could not check {key}: {exc}") from exc
    return _local_path(key).exists()
