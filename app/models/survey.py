"""Onboarding questions managed from the admin panel, and each user's answers."""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, pg_enum


class SurveyQuestionKind(str, enum.Enum):
    SINGLE = "single"
    MULTI = "multi"
    TILES = "tiles"
    TEXT = "text"


class SurveyQuestion(TimestampMixin, Base):
    __tablename__ = "survey_questions"
    __table_args__ = (Index("ix_survey_questions_sort_order", "sort_order"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text)
    placeholder: Mapped[str | None] = mapped_column(String(300))
    kind: Mapped[SurveyQuestionKind] = mapped_column(
        pg_enum(SurveyQuestionKind, "survey_question_kind"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_skip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    options: Mapped[list["SurveyOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="SurveyOption.sort_order",
        lazy="selectin",
    )


class SurveyOption(TimestampMixin, Base):
    __tablename__ = "survey_options"
    __table_args__ = (
        Index("ix_survey_options_question_id", "question_id"),
        UniqueConstraint("question_id", "label", name="uq_survey_options_question_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("survey_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    clears_others: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped[SurveyQuestion] = relationship(back_populates="options")


class SurveyAnswer(TimestampMixin, Base):
    """One chosen option, or one free-text reply, kept on the user."""

    __tablename__ = "survey_answers"
    __table_args__ = (Index("ix_survey_answers_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("survey_questions.id", ondelete="SET NULL"),
    )
    option_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("survey_options.id", ondelete="SET NULL"),
    )
    question_title: Mapped[str] = mapped_column(String(200), nullable=False)
    question_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    value_text: Mapped[str] = mapped_column(String(300), nullable=False)
