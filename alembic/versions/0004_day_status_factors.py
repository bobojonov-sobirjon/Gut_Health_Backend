"""Store the tracking start date, onboarding flag, and diary factor chips.

Revision ID: 0004_day_status_factors
Revises: 0003_devices_admin
Create Date: 2026-10-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_day_status_factors"
down_revision: Union[str, Sequence[str], None] = "0003_devices_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("tracking_started_on", sa.Date(), nullable=True))
    op.add_column(
        "diary_entries",
        sa.Column(
            "factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE users AS account
        SET onboarding_completed = true,
            tracking_started_on = COALESCE(
                account.tracking_started_on,
                (SELECT MIN(profile.created_at)::date FROM onboarding_profiles AS profile WHERE profile.user_id = account.id),
                (SELECT MIN(entry.date) FROM diary_entries AS entry WHERE entry.user_id = account.id)
            )
        WHERE EXISTS (
            SELECT 1 FROM onboarding_profiles AS profile WHERE profile.user_id = account.id
        )
        OR EXISTS (
            SELECT 1 FROM diary_entries AS entry WHERE entry.user_id = account.id
        )
        """
    )


def downgrade() -> None:
    op.drop_column("diary_entries", "factors")
    op.drop_column("users", "tracking_started_on")
    op.drop_column("users", "onboarding_completed")
