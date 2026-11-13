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

import re
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class StorageError(RuntimeError):
    """The object store could not be reached, or is misconfigured."""


_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

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


def object_key(workspace_id: uuid.UUID, filename: str) -> str:
    """Where one upload lives in the bucket.

    Prefixed by workspace so an object's tenant is visible from its key alone,
    which makes an accidental cross-tenant read obvious in logs and lets an
    IAM policy or lifecycle rule be written per prefix later. The random
    segment keeps two uploads of `receipt.jpg` apart.
    """
    return f"ws/{workspace_id}/{uuid.uuid4()}-{safe_filename(filename)}"


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


def presigned_get_url(key: str) -> str | None:
    """A short-lived URL for viewing one object, or None on `local`."""
    if settings.storage_backend != "s3":
        return None
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": key},
            ExpiresIn=settings.presigned_url_ttl_seconds,
        )
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - needs AWS
        raise StorageError(f"Could not presign a download for {key}: {exc}") from exc


# --- local backend ---------------------------------------------------------


def _local_path(key: str) -> Path:
    """The file backing one key, with the key's own directories flattened.

    The key is already sanitised by `object_key`, but this is the one place a
    key becomes a filesystem path, so it re-checks rather than trusting that:
    a key is one path segment here, never a directory walk.
    """
    flattened = key.replace("/", "__")
    if flattened != safe_filename(flattened):
        raise StorageError(f"Refusing to write an unsafe key: {key!r}")
    return Path(settings.local_upload_dir) / flattened


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
