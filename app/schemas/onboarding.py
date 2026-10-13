"""Onboarding request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_labels(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        label = item.strip()
        if not label:
            raise ValueError("Items cannot be blank")
        key = label.casefold()
        if key in seen:
            raise ValueError("Items must be unique")
        seen.add(key)
        cleaned.append(label)
    return cleaned


class OnboardingWrite(BaseModel):
    """Full onboarding document. PUT creates the row or replaces it."""

    model_config = ConfigDict(extra="forbid")

    goals: list[str] = Field(default_factory=list, max_length=20)
    concerns: list[str] = Field(default_factory=list, max_length=20)
    interests: list[str] = Field(default_factory=list, max_length=20)
    target_30_day_goal: str | None = Field(default=None, max_length=300)

    @field_validator("goals", "concerns", "interests")
    @classmethod
    def clean_labels(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item.strip()) > 80:
                raise ValueError("Each item must be 80 characters or fewer")
        return _clean_labels(value)

    @field_validator("target_30_day_goal")
    @classmethod
    def clean_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class OnboardingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    goals: list[str]
    concerns: list[str]
    interests: list[str]
    target_30_day_goal: str | None
    created_at: datetime
    updated_at: datetime
