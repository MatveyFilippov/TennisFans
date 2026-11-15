from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TENNISFANS_", extra="ignore")

    database_url: SecretStr
    session_secret: SecretStr
    media_root: Path = Path("media")
    environment: Literal["development", "production", "test"] = "development"
    public_url: str = "http://localhost:8000"
    allowed_origins: list[str] = ["http://localhost:5173"]
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(8000, ge=1, le=65535)
    trusted_proxy_hosts: str = "127.0.0.1"
    secure_cookies: bool = False
    same_site: Literal["lax", "strict", "none"] = "lax"
    session_hours: int = Field(168, ge=1, le=720)
    reset_minutes: int = Field(30, ge=1, le=120)
    elo_k: int = Field(32, ge=1, le=100)
    upload_bytes: int = Field(12 * 1024**2, ge=1024)
    upload_request_bytes: int = Field(64 * 1024**2, ge=1024)
    storage_quota_bytes: int = Field(0, ge=0)
    image_pixels: int = Field(25_000_000, ge=1, le=50_000_000)
    reconcile_seconds: int = Field(30, ge=1, le=60)
    pool_size: int = Field(8, ge=1, le=100)
    statement_timeout_ms: int = Field(30_000, ge=1000)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] | None = None
    build_sha: str = "local"

    @model_validator(mode="after")
    def validate_deployment(self) -> "Settings":
        db = make_url(self.database_url.get_secret_value())
        if db.drivername != "postgresql+psycopg" or not db.database:
            raise ValueError(
                "Use an existing PostgreSQL database with the postgresql+psycopg driver"
            )
        if len(self.session_secret.get_secret_value()) < 32:
            raise ValueError("Set a random session secret of at least 32 characters")
        for origin in [self.public_url, *self.allowed_origins]:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError(
                    "Configure literal HTTP(S) origins without a path or trailing slash"
                )
        if self.same_site == "none" and not self.secure_cookies:
            raise ValueError("Cross-site cookies require Secure")
        if self.environment == "production" and (
            not self.secure_cookies
            or any(
                not url.startswith("https://") for url in [self.public_url, *self.allowed_origins]
            )
        ):
            raise ValueError("Production requires HTTPS origins and Secure cookies")
        if self.upload_bytes > self.upload_request_bytes:
            raise ValueError("The upload request limit must cover at least one file")
        return self
