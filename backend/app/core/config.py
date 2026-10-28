from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables / .env.

    Never read os.environ directly elsewhere in the app — add the value here
    so there is one list of everything the service needs to run.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = "development"
    secret_key: str = "change-me-in-dev"

    # Inside Docker Compose the host is the service name `db`, not localhost.
    database_url: str = "postgresql://warranty:warranty@localhost:5432/warrantytrack"

    # Where the browser calls from. Add the deployed origin before release.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Where this API is reachable. Only used to build the dev upload URL
    # below; in production the browser uploads to S3, not to us.
    api_base_url: str = "http://localhost:8000"

    # AWS — left blank until the account exists. See infra/README.md.
    aws_region: str = "ap-southeast-1"
    s3_bucket_name: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    ses_sender_email: str | None = None

    # --- Which implementation each outside service uses -------------------
    #
    # Defaults are the local ones, so `docker compose up` gives a working
    # receipt-upload and OCR flow with no AWS account and no spend — which
    # matters while the project budget is 4,000 THB for the semester. Flip each
    # to the real backend once the account exists:
    #
    #   STORAGE_BACKEND=s3  OCR_BACKEND=textract  EMAIL_BACKEND=ses
    #
    # `local` storage keeps uploads on the API container's disk, `fake` OCR
    # returns canned fields, and `log` email writes the message to the log.
    # None of the three is allowed in production — see the check below.
    storage_backend: Literal["s3", "local"] = "local"
    ocr_backend: Literal["textract", "fake"] = "fake"
    email_backend: Literal["ses", "log"] = "log"

    # How long a presigned S3 URL stays valid. Short on purpose: the bucket is
    # private and a leaked URL is a leaked object until it expires.
    presigned_url_ttl_seconds: int = 900

    # Where `local` storage writes. Inside the container, so it disappears
    # with the container — which is what you want for scratch uploads.
    local_upload_dir: str = "/tmp/warrantytrack-uploads"

    def model_post_init(self, _context: object) -> None:
        """Refuse to start in production on the development backends.

        Each of them is a quiet wrong answer rather than an error: `local`
        storage would accept uploads onto a container's disk and lose them on
        the next deploy, `fake` OCR would invent an invoice, and `log` email
        would silently not warn anyone that their warranty is expiring. Failing
        at startup is the only safe behaviour.
        """
        if self.environment != "production":
            return

        development_backends = {
            "STORAGE_BACKEND": self.storage_backend == "local",
            "OCR_BACKEND": self.ocr_backend == "fake",
            "EMAIL_BACKEND": self.email_backend == "log",
        }
        active = [name for name, is_development in development_backends.items() if is_development]
        if active:
            raise RuntimeError(
                "Development backends are active in production: "
                + ", ".join(sorted(active))
                + ". Set them to s3 / textract / ses."
            )
        if not self.s3_bucket_name:
            raise RuntimeError("S3_BUCKET_NAME is required in production.")


settings = Settings()
