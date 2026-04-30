"""Application configuration loaded from environment variables."""

import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "CHANGE_ME_in_production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    app_title: str = "4'S Cloud Studio API"
    app_version: str = "0.1.0"
    debug: bool = False

    # --- JWT ---
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- PostgreSQL (async DSN) ---
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/foursdb"

    # --- S3-compatible Storage ---
    s3_endpoint_url: str = "https://s3.amazonaws.com"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "4s-cloud-studio"
    s3_region_name: str = "us-east-1"

    # --- CORS ---
    cors_origins: list[str] = ["*"]


settings = Settings()

if settings.jwt_secret_key == _DEFAULT_JWT_SECRET:
    warnings.warn(
        "JWT_SECRET_KEY is using the default placeholder value. "
        "Set a strong secret in your .env file before deploying.",
        stacklevel=1,
    )
