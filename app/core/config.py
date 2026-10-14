"""Runtime settings loaded from the environment and an optional .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Process-wide configuration. Required secrets have no insecure default."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Gut Health Tracker"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=14, ge=1, le=90)

    media_root: str = "app/media"
    media_url_prefix: str = "/media"
    public_base_url: str = "http://localhost:8009"
    max_upload_bytes: int = Field(default=5_242_880, ge=1)

    cors_origins: str = "*"

    firebase_type: str = "service_account"
    firebase_project_id: str = ""
    firebase_private_key_id: str = ""
    firebase_private_key: str = ""
    firebase_client_email: str = ""
    firebase_client_id: str = ""
    firebase_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    firebase_token_uri: str = "https://oauth2.googleapis.com/token"
    firebase_auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    firebase_client_x509_cert_url: str = ""
    firebase_universe_domain: str = "googleapis.com"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    email_code_expire_minutes: int = Field(default=10, ge=1, le=60)

    admin_email: str = ""
    admin_password: str = ""
    docs_enabled: bool = True

    @field_validator("database_url")
    @classmethod
    def require_async_postgres(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with postgresql+asyncpg://")
        return value

    @field_validator("public_base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("media_url_prefix")
    @classmethod
    def normalize_media_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("MEDIA_URL_PREFIX must start with /")
        return value.rstrip("/") or "/media"

    @field_validator("firebase_private_key")
    @classmethod
    def normalize_private_key(cls, value: str) -> str:
        value = value.strip().strip('"')
        return value.replace("\\n", "\n")

    @field_validator("api_v1_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with /")
        return value.rstrip("/") or "/api/v1"

    @model_validator(mode="after")
    def check_production_safety(self) -> Self:
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("DEBUG must be false in production")
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS cannot contain * in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def firebase_enabled(self) -> bool:
        return bool(self.firebase_project_id and self.firebase_private_key and self.firebase_client_email)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def media_dir(self) -> Path:
        path = Path(self.media_root)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
