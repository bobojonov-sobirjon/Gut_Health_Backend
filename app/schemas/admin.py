"""Admin panel list and detail schemas. Detail models expose every stored field."""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from app.models.device import DevicePlatform
from app.models.diary import FoodDrinkKind
from app.models.user import AuthProvider, UploadPurpose
from app.schemas.auth import normalize_email
from app.schemas.device import DeviceRead
from app.schemas.survey import SurveyAnswerGroup
from app.services.storage_service import to_public_url


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_admin_email(cls, value: object) -> object:
        return normalize_email(value)


class AdminProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    auth_provider: AuthProvider
    created_at: datetime
    updated_at: datetime


class AdminLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    admin: AdminProfile


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class AdminStats(BaseModel):
    users: int
    active_users: int
    admins: int
    devices: int
    active_devices: int
    onboarding_profiles: int
    diary_entries: int
    bowel_movements: int
    food_drinks: int
    uploads: int


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    auth_provider: AuthProvider
    provider_subject: str | None
    avatar_url: str | None
    is_active: bool
    is_admin: bool
    onboarding_completed: bool
    tracking_started_on: date | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("avatar_url")
    def serialize_avatar_url(self, value: str | None) -> str | None:
        return to_public_url(value)


class AdminUserPage(PageMeta):
    items: list[AdminUserListItem]


class AdminUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    stored_path: str
    purpose: UploadPurpose
    created_at: datetime
    url: str | None = None

    @field_serializer("url")
    def serialize_url(self, value: str | None) -> str | None:
        return value


class AdminOnboardingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_email: str | None = None
    goals: list[str]
    concerns: list[str]
    interests: list[str]
    target_30_day_goal: str | None
    created_at: datetime
    updated_at: datetime


class AdminOnboardingPage(PageMeta):
    items: list[AdminOnboardingRead]


class AdminBowelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    diary_entry_id: UUID
    occurred_at: time
    bristol_type: int
    pain_level: int
    blood_present: bool
    created_at: datetime
    updated_at: datetime


class AdminBowelListItem(AdminBowelRead):
    user_id: UUID
    user_email: str
    entry_date: date


class AdminBowelPage(PageMeta):
    items: list[AdminBowelListItem]


class AdminFoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    diary_entry_id: UUID
    kind: FoodDrinkKind
    name: str
    consumed_at: time | None
    notes: str | None
    photo_url: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("photo_url")
    def serialize_photo_url(self, value: str | None) -> str | None:
        return to_public_url(value)


class AdminFoodListItem(AdminFoodRead):
    user_id: UUID
    user_email: str
    entry_date: date


class AdminFoodPage(PageMeta):
    items: list[AdminFoodListItem]


class AdminDiaryListItem(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    entry_date: date
    no_bowel_movement: bool
    stress_level: int | None
    sleep_hours: float | None
    exercise_minutes: int | None
    water_ml: int | None
    other_factors: str | None
    factors: list[str]
    bowel_movement_count: int
    food_drink_count: int
    created_at: datetime
    updated_at: datetime


class AdminDiaryPage(PageMeta):
    items: list[AdminDiaryListItem]


class AdminDiaryDetail(AdminDiaryListItem):
    bowel_movements: list[AdminBowelRead]
    food_drinks: list[AdminFoodRead]


class AdminDeviceRead(DeviceRead):
    user_email: str


class AdminDevicePage(PageMeta):
    items: list[AdminDeviceRead]


class AdminDiarySummary(BaseModel):
    id: UUID
    entry_date: date
    no_bowel_movement: bool
    bowel_movement_count: int
    food_drink_count: int
    created_at: datetime
    updated_at: datetime


class AdminUserDetail(AdminUserListItem):
    devices: list[DeviceRead]
    onboarding: AdminOnboardingRead | None
    survey_answers: list[SurveyAnswerGroup] = Field(default_factory=list)
    diary_entries: list[AdminDiarySummary]
    uploads: list[AdminUploadRead]
    device_count: int
    diary_count: int
    upload_count: int
