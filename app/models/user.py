"""Account, refresh-session, and uploaded-file persistence."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, pg_enum, utcnow


class AuthProvider(str, enum.Enum):
    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"


class UploadPurpose(str, enum.Enum):
    AVATAR = "avatar"
    LOG = "log"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_created_at", "created_at"),
        Index(
            "uq_users_provider_subject",
            "auth_provider",
            "provider_subject",
            unique=True,
            postgresql_where=text("provider_subject IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(512))
    full_name: Mapped[str | None] = mapped_column(String(120))
    auth_provider: Mapped[AuthProvider] = mapped_column(
        pg_enum(AuthProvider, "auth_provider"),
        default=AuthProvider.EMAIL,
        nullable=False,
    )
    provider_subject: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracking_started_on: Mapped[date | None] = mapped_column(Date)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    onboarding_profile: Mapped["OnboardingProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        uselist=False,
    )
    diary_entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    devices: Mapped[list["UserDevice"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_created_at", "created_at"),)

    jti: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens", lazy="raise")


class UploadedFile(Base):
    """Binary file saved under media/, with the public path stored in PostgreSQL."""

    __tablename__ = "uploaded_files"
    __table_args__ = (
        UniqueConstraint("stored_path", name="uq_uploaded_files_stored_path"),
        Index("ix_uploaded_files_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    purpose: Mapped[UploadPurpose] = mapped_column(
        pg_enum(UploadPurpose, "upload_purpose"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="uploaded_files", lazy="raise")


class EmailLoginCode(Base):
    """One-time sign-in code for passwordless email login."""

    __tablename__ = "email_login_codes"
    __table_args__ = (
        Index("ix_email_login_codes_email", "email"),
        Index("ix_email_login_codes_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
