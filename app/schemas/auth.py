"""Authentication and profile schemas."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from app.models.user import AuthProvider
from app.services.storage_service import to_public_url


def normalize_email(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def require_password_complexity(value: str) -> str:
    if not any(character.isalpha() for character in value) or not any(
        character.isdigit() for character in value
    ):
        raise ValueError("Password must include at least one letter and one number")
    return value


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_register_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return require_password_complexity(value)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return clean_name(value)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_login_email(cls, value: object) -> object:
        return normalize_email(value)


class FirebaseAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_token: str = Field(min_length=20, max_length=8192)


class EmailSendCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_send_email(cls, value: object) -> object:
        return normalize_email(value)


class EmailVerifyCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_verify_email(cls, value: object) -> object:
        return normalize_email(value)


class EmailCodeResponse(BaseModel):
    detail: str
    expires_in: int
    debug_code: str | None = None


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)


class LogoutRequest(RefreshRequest):
    """Same body as refresh: the refresh token to revoke."""


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return clean_name(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    auth_provider: AuthProvider
    provider_subject: str | None
    avatar_url: str | None
    onboarding_completed: bool
    tracking_started_on: date | None
    created_at: datetime

    @field_serializer("avatar_url")
    def serialize_avatar_url(self, value: str | None) -> str | None:
        return to_public_url(value)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AuthResponse(TokenResponse):
    user: UserRead
