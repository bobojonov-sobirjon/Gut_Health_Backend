"""Survey question editor and the answers stored on a user."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.survey import SurveyQuestionKind


class SurveyOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    emoji: str | None
    sort_order: int
    is_active: bool
    clears_others: bool


class SurveyQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    placeholder: str | None
    kind: SurveyQuestionKind
    sort_order: int
    is_active: bool
    is_required: bool
    allow_skip: bool
    options: list[SurveyOptionRead]


class SurveyQuestionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=1000)
    placeholder: str | None = Field(default=None, max_length=300)
    kind: SurveyQuestionKind
    sort_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True
    is_required: bool = False
    allow_skip: bool = True

    @field_validator("title", "subtitle", "placeholder")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SurveyQuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=1000)
    placeholder: str | None = Field(default=None, max_length=300)
    kind: SurveyQuestionKind | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999)
    is_active: bool | None = None
    is_required: bool | None = None
    allow_skip: bool | None = None


class SurveyOptionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    emoji: str | None = Field(default=None, max_length=16)
    sort_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True
    clears_others: bool = False

    @field_validator("label", "emoji")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SurveyOptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=120)
    emoji: str | None = Field(default=None, max_length=16)
    sort_order: int | None = Field(default=None, ge=0, le=999)
    is_active: bool | None = None
    clears_others: bool | None = None


class SurveyAnswerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    option_ids: list[UUID] = Field(default_factory=list, max_length=30)
    text_value: str | None = Field(default=None, max_length=300)

    @field_validator("text_value")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SurveyAnswerGroup(BaseModel):
    question_id: UUID | None
    question_title: str
    question_kind: str
    values: list[str]


class UserSurveyRead(BaseModel):
    user_id: UUID
    user_email: str
    full_name: str | None
    answers: list[SurveyAnswerGroup]
    updated_at: datetime | None
