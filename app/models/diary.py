"""One diary row per user per calendar day, with bowel logs, food, and factors."""

import enum
import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, pg_enum


class FoodDrinkKind(str, enum.Enum):
    FOOD = "food"
    DRINK = "drink"


class DiaryFactor(str, enum.Enum):
    STRESS = "stress"
    SLEEP = "sleep"
    EXERCISE = "exercise"
    LOW_WATER = "low_water"


class DiaryEntry(TimestampMixin, Base):
    __tablename__ = "diary_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_diary_entries_user_date"),
        Index("ix_diary_entries_user_id", "user_id"),
        Index("ix_diary_entries_date", "date"),
        Index("ix_diary_entries_created_at", "created_at"),
        Index("ix_diary_entries_updated_at", "updated_at"),
        CheckConstraint(
            "stress_level IS NULL OR stress_level BETWEEN 0 AND 10",
            name="ck_diary_entries_stress",
        ),
        CheckConstraint(
            "sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)",
            name="ck_diary_entries_sleep",
        ),
        CheckConstraint(
            "exercise_minutes IS NULL OR (exercise_minutes >= 0 AND exercise_minutes <= 1440)",
            name="ck_diary_entries_exercise",
        ),
        CheckConstraint(
            "water_ml IS NULL OR (water_ml >= 0 AND water_ml <= 20000)",
            name="ck_diary_entries_water",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_date: Mapped[date] = mapped_column("date", Date, nullable=False)
    no_bowel_movement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stress_level: Mapped[int | None] = mapped_column(SmallInteger)
    sleep_hours: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    exercise_minutes: Mapped[int | None] = mapped_column(Integer)
    water_ml: Mapped[int | None] = mapped_column(Integer)
    other_factors: Mapped[str | None] = mapped_column(Text)
    factors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    user: Mapped["User"] = relationship(back_populates="diary_entries", lazy="raise")
    bowel_movements: Mapped[list["BowelMovement"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="BowelMovement.occurred_at",
    )
    food_drinks: Mapped[list["FoodDrinkLog"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="FoodDrinkLog.consumed_at",
    )


class BowelMovement(TimestampMixin, Base):
    __tablename__ = "bowel_movements"
    __table_args__ = (
        Index("ix_bowel_movements_diary_entry_id", "diary_entry_id"),
        Index("ix_bowel_movements_created_at", "created_at"),
        CheckConstraint("bristol_type BETWEEN 1 AND 7", name="ck_bowel_movements_bristol"),
        CheckConstraint("pain_level BETWEEN 0 AND 10", name="ck_bowel_movements_pain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    diary_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("diary_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    occurred_at: Mapped[time] = mapped_column(Time, nullable=False)
    bristol_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pain_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    blood_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    entry: Mapped[DiaryEntry] = relationship(back_populates="bowel_movements", lazy="raise")


class FoodDrinkLog(TimestampMixin, Base):
    __tablename__ = "food_drink_logs"
    __table_args__ = (
        Index("ix_food_drink_logs_diary_entry_id", "diary_entry_id"),
        Index("ix_food_drink_logs_created_at", "created_at"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_food_drink_logs_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    diary_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("diary_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[FoodDrinkKind] = mapped_column(pg_enum(FoodDrinkKind, "food_drink_kind"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    consumed_at: Mapped[time | None] = mapped_column(Time)
    notes: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))

    entry: Mapped[DiaryEntry] = relationship(back_populates="food_drinks", lazy="raise")
