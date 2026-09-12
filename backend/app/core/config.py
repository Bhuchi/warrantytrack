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

    # AWS — left blank until the account exists. See infra/README.md.
    aws_region: str = "ap-southeast-1"
    s3_bucket_name: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    ses_sender_email: str | None = None


settings = Settings()
