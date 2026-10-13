"""Create users, onboarding, uploads, and diary tables.

Revision ID: 0001_foundation_diary
Revises:
Create Date: 2026-10-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation_diary"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AUTH_PROVIDER_VALUES = ("email", "google", "apple")
UPLOAD_PURPOSE_VALUES = ("avatar", "log")
FOOD_DRINK_VALUES = ("food", "drink")


def upgrade() -> None:
    auth_provider = postgresql.ENUM(*AUTH_PROVIDER_VALUES, name="auth_provider", create_type=False)
    upload_purpose = postgresql.ENUM(*UPLOAD_PURPOSE_VALUES, name="upload_purpose", create_type=False)
    food_drink_kind = postgresql.ENUM(*FOOD_DRINK_VALUES, name="food_drink_kind", create_type=False)
    bind = op.get_bind()
    auth_provider.create(bind, checkfirst=True)
    upload_purpose.create(bind, checkfirst=True)
    food_drink_kind.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=512), nullable=True),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column(
            "auth_provider",
            auth_provider,
            nullable=False,
            server_default="email",
        ),
        sa.Column("provider_subject", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"])
    op.create_index(
        "uq_users_provider_subject",
        "users",
        ["auth_provider", "provider_subject"],
        unique=True,
        postgresql_where=sa.text("provider_subject IS NOT NULL"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("jti", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_created_at", "refresh_tokens", ["created_at"])

    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("purpose", upload_purpose, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stored_path", name="uq_uploaded_files_stored_path"),
    )
    op.create_index("ix_uploaded_files_user_id", "uploaded_files", ["user_id"])
    op.create_index("ix_uploaded_files_created_at", "uploaded_files", ["created_at"])

    op.create_table(
        "onboarding_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goals", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("concerns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("interests", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_30_day_goal", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_onboarding_profiles_user_id"),
    )
    op.create_index("ix_onboarding_profiles_created_at", "onboarding_profiles", ["created_at"])

    op.create_table(
        "diary_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("no_bowel_movement", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stress_level", sa.SmallInteger(), nullable=True),
        sa.Column("sleep_hours", sa.Numeric(3, 1), nullable=True),
        sa.Column("exercise_minutes", sa.Integer(), nullable=True),
        sa.Column("water_ml", sa.Integer(), nullable=True),
        sa.Column("other_factors", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "date", name="uq_diary_entries_user_date"),
        sa.CheckConstraint(
            "stress_level IS NULL OR stress_level BETWEEN 0 AND 10",
            name="ck_diary_entries_stress",
        ),
        sa.CheckConstraint(
            "sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)",
            name="ck_diary_entries_sleep",
        ),
        sa.CheckConstraint(
            "exercise_minutes IS NULL OR (exercise_minutes >= 0 AND exercise_minutes <= 1440)",
            name="ck_diary_entries_exercise",
        ),
        sa.CheckConstraint(
            "water_ml IS NULL OR (water_ml >= 0 AND water_ml <= 20000)",
            name="ck_diary_entries_water",
        ),
    )
    op.create_index("ix_diary_entries_user_id", "diary_entries", ["user_id"])
    op.create_index("ix_diary_entries_date", "diary_entries", ["date"])
    op.create_index("ix_diary_entries_created_at", "diary_entries", ["created_at"])

    op.create_table(
        "bowel_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("diary_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.Time(), nullable=False),
        sa.Column("bristol_type", sa.SmallInteger(), nullable=False),
        sa.Column("pain_level", sa.SmallInteger(), nullable=False),
        sa.Column("blood_present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["diary_entry_id"], ["diary_entries.id"], ondelete="CASCADE"),
        sa.CheckConstraint("bristol_type BETWEEN 1 AND 7", name="ck_bowel_movements_bristol"),
        sa.CheckConstraint("pain_level BETWEEN 0 AND 10", name="ck_bowel_movements_pain"),
    )
    op.create_index("ix_bowel_movements_diary_entry_id", "bowel_movements", ["diary_entry_id"])
    op.create_index("ix_bowel_movements_created_at", "bowel_movements", ["created_at"])

    op.create_table(
        "food_drink_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("diary_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", food_drink_kind, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("consumed_at", sa.Time(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["diary_entry_id"], ["diary_entries.id"], ondelete="CASCADE"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_food_drink_logs_name"),
    )
    op.create_index("ix_food_drink_logs_diary_entry_id", "food_drink_logs", ["diary_entry_id"])
    op.create_index("ix_food_drink_logs_created_at", "food_drink_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_food_drink_logs_created_at", table_name="food_drink_logs")
    op.drop_index("ix_food_drink_logs_diary_entry_id", table_name="food_drink_logs")
    op.drop_table("food_drink_logs")
    op.drop_index("ix_bowel_movements_created_at", table_name="bowel_movements")
    op.drop_index("ix_bowel_movements_diary_entry_id", table_name="bowel_movements")
    op.drop_table("bowel_movements")
    op.drop_index("ix_diary_entries_created_at", table_name="diary_entries")
    op.drop_index("ix_diary_entries_date", table_name="diary_entries")
    op.drop_index("ix_diary_entries_user_id", table_name="diary_entries")
    op.drop_table("diary_entries")
    op.drop_index("ix_onboarding_profiles_created_at", table_name="onboarding_profiles")
    op.drop_table("onboarding_profiles")
    op.drop_index("ix_uploaded_files_created_at", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_user_id", table_name="uploaded_files")
    op.drop_table("uploaded_files")
    op.drop_index("ix_refresh_tokens_created_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("uq_users_provider_subject", table_name="users")
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_table("users")
    bind = op.get_bind()
    postgresql.ENUM(name="food_drink_kind").drop(bind, checkfirst=True)
    postgresql.ENUM(name="upload_purpose").drop(bind, checkfirst=True)
    postgresql.ENUM(name="auth_provider").drop(bind, checkfirst=True)
