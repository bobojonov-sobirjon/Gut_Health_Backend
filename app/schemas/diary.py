"""Diary request and response schemas."""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.diary import DiaryFactor, FoodDrinkKind
from app.services.storage_service import to_public_url


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _factors(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    allowed = {item.value for item in DiaryFactor}
    cleaned: list[str] = []
    for item in values:
        token = item.strip().lower()
        if token not in allowed:
            raise ValueError("Factor must be stress, sleep, exercise, or low_water")
        if token not in cleaned:
            cleaned.append(token)
    return cleaned


class BowelMovementWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_at: time
    bristol_type: int = Field(ge=1, le=7, description="Bristol stool scale, 1 (hard) through 7 (liquid).")
    pain_level: int = Field(ge=0, le=10)
    blood_present: bool = False


class FoodDrinkWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FoodDrinkKind
    name: str = Field(min_length=1, max_length=200)
    consumed_at: time | None = None
    notes: str | None = Field(default=None, max_length=2000)
    photo_url: str | None = Field(
        default=None,
        max_length=500,
        description="Stored path or absolute URL returned by the upload endpoint.",
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("notes", "photo_url")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_text(value)


class DiaryEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_date: date
    no_bowel_movement: bool = False
    stress_level: int | None = Field(default=None, ge=0, le=10)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    exercise_minutes: int | None = Field(default=None, ge=0, le=1440)
    water_ml: int | None = Field(default=None, ge=0, le=20000)
    other_factors: str | None = Field(default=None, max_length=2000)
    factors: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Selected factor chips: stress, sleep, exercise, low_water.",
    )
    bowel_movements: list[BowelMovementWrite] = Field(default_factory=list, max_length=20)
    food_drinks: list[FoodDrinkWrite] = Field(default_factory=list, max_length=50)

    @field_validator("sleep_hours")
    @classmethod
    def round_sleep(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 1)

    @field_validator("other_factors")
    @classmethod
    def clean_other(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("factors")
    @classmethod
    def clean_factors(cls, value: list[str]) -> list[str]:
        return _factors(value) or []


class DiaryEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_date: date | None = None
    no_bowel_movement: bool | None = None
    stress_level: int | None = Field(default=None, ge=0, le=10)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    exercise_minutes: int | None = Field(default=None, ge=0, le=1440)
    water_ml: int | None = Field(default=None, ge=0, le=20000)
    other_factors: str | None = Field(default=None, max_length=2000)
    factors: list[str] | None = Field(default=None, max_length=4)
    bowel_movements: list[BowelMovementWrite] | None = Field(default=None, max_length=20)
    food_drinks: list[FoodDrinkWrite] | None = Field(default=None, max_length=50)

    @field_validator("sleep_hours")
    @classmethod
    def round_sleep(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 1)

    @field_validator("other_factors")
    @classmethod
    def clean_other(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("factors")
    @classmethod
    def clean_factors(cls, value: list[str] | None) -> list[str] | None:
        return _factors(value)


class BowelMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: time
    bristol_type: int
    pain_level: int
    blood_present: bool
    created_at: datetime


class FoodDrinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: FoodDrinkKind
    name: str
    consumed_at: time | None
    notes: str | None
    photo_url: str | None
    created_at: datetime

    @field_serializer("photo_url")
    def serialize_photo_url(self, value: str | None) -> str | None:
        return to_public_url(value)


class DiaryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_date: date
    no_bowel_movement: bool
    stress_level: int | None
    sleep_hours: float | None
    exercise_minutes: int | None
    water_ml: int | None
    other_factors: str | None
    factors: list[str]
    bowel_movements: list[BowelMovementRead]
    food_drinks: list[FoodDrinkRead]
    created_at: datetime
    updated_at: datetime


class DiaryCalendarItem(BaseModel):
    entry_date: date
    day_status: Literal["tracked", "missed", "open", "before_start", "future"]
    stool_status: Literal["logged", "none", "unknown"]
    has_entry: bool
    no_bowel_movement: bool
    bowel_movement_count: int
    food_drink_count: int
    created_at: datetime | None


class DiaryCalendarResponse(BaseModel):
    tracking_started_on: date | None
    items: list[DiaryCalendarItem]
    total: int


class DiarySyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    since: datetime | None = None
    entries: list[DiaryEntryCreate] = Field(default_factory=list, max_length=90)

    @field_validator("since")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("since must include a timezone offset")
        return value


class DiarySyncResponse(BaseModel):
    server_time: datetime
    entries: list[DiaryEntryRead]
