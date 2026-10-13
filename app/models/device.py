"""Push-notification device tokens registered by the mobile app."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, pg_enum
from app.models.user import User


class DevicePlatform(str, enum.Enum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class UserDevice(TimestampMixin, Base):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("token", name="uq_user_devices_token"),
        Index("ix_user_devices_user_id", "user_id"),
        Index("ix_user_devices_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[DevicePlatform] = mapped_column(
        pg_enum(DevicePlatform, "device_platform"),
        nullable=False,
    )
    device_name: Mapped[str | None] = mapped_column(String(120))
    app_version: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="devices", lazy="raise")
