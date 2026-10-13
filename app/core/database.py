"""Async SQLAlchemy engine, sessions, and shared model mixins."""

import enum
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings
from app.core.exceptions import conflict

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Declarative base for all persistence models."""


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """PostgreSQL enum that stores the member value, not the member name."""

    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Created and updated timestamps maintained by the ORM and the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


def _constraint_name(exc: IntegrityError) -> str:
    candidates: list[BaseException | None] = [exc, getattr(exc, "orig", None)]
    orig = getattr(exc, "orig", None)
    if orig is not None:
        candidates.append(getattr(orig, "__cause__", None))
        candidates.append(getattr(orig, "orig", None))
    for candidate in candidates:
        if candidate is None:
            continue
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    return ""


async def commit_session(
    session: AsyncSession,
    conflicts: dict[str, str] | None = None,
) -> None:
    """Commit the current transaction and map unique violations to HTTP 409."""

    conflict_messages = conflicts or {}
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        name = _constraint_name(exc)
        if not name:
            message = str(exc)
            for constraint, detail in conflict_messages.items():
                if constraint in message:
                    logger.warning("Database integrity conflict (%s)", constraint)
                    raise conflict(detail) from exc
        detail = conflict_messages.get(
            name,
            "This record conflicts with an existing one",
        )
        logger.warning("Database integrity conflict (%s)", name or "unknown")
        raise conflict(detail) from exc


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session and roll back any work left open by the request."""

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            try:
                await session.rollback()
            except Exception:
                logger.warning("Session rollback failed", exc_info=True)
            raise
