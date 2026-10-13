"""Onboarding answers captured once per user and updated in place."""

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.user import User


class OnboardingProfile(TimestampMixin, Base):
    __tablename__ = "onboarding_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_onboarding_profiles_user_id"),
        Index("ix_onboarding_profiles_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    goals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    concerns: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    interests: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    target_30_day_goal: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship(back_populates="onboarding_profile", lazy="raise")
