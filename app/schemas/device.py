"""Push device token request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.device import DevicePlatform


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class DeviceUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=10, max_length=512)
    platform: DevicePlatform
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)

    @field_validator("token")
    @classmethod
    def clean_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Token cannot be blank")
        return value

    @field_validator("device_name", "app_version")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean(value)


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: DevicePlatform | None = None
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None

    @field_validator("device_name", "app_version")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean(value)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    token: str
    platform: DevicePlatform
    device_name: str | None
    app_version: str | None
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
