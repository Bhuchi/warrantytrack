"""Presigned S3 URLs must use the bucket's regional endpoint."""

from urllib.parse import urlparse

import boto3

from app.core.config import settings
from app.services import storage


def test_presigned_urls_use_regional_s3_host(monkeypatch):
    real_client = boto3.client

    def client_with_test_credentials(service_name, **kwargs):
        return real_client(
            service_name,
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            **kwargs,
        )

    monkeypatch.setattr(storage.boto3, "client", client_with_test_credentials)
    monkeypatch.setattr(storage, "_s3_client", None)
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "aws_region", "ap-southeast-1")
    monkeypatch.setattr(settings, "s3_bucket_name", "warrantytrack-documents-example")

    put_url = storage.presigned_put_url("ws/example/receipt.png", "image/png")
    get_url = storage.presigned_get_url("ws/example/receipt.png")

    expected_host = "warrantytrack-documents-example.s3.ap-southeast-1.amazonaws.com"
    assert urlparse(put_url).hostname == expected_host
    assert urlparse(get_url).hostname == expected_host
