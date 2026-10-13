"""Allow passwordless users and store email sign-in codes.

Revision ID: 0002_firebase_auth
Revises: 0001_foundation_diary
Create Date: 2026-10-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_firebase_auth"
down_revision: Union[str, Sequence[str], None] = "0001_foundation_diary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=512), nullable=True)
    op.create_table(
        "email_login_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_email_login_codes_email", "email_login_codes", ["email"])
    op.create_index("ix_email_login_codes_created_at", "email_login_codes", ["created_at"])
    op.create_index("ix_diary_entries_updated_at", "diary_entries", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_diary_entries_updated_at", table_name="diary_entries")
    op.drop_index("ix_email_login_codes_created_at", table_name="email_login_codes")
    op.drop_index("ix_email_login_codes_email", table_name="email_login_codes")
    op.drop_table("email_login_codes")
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=512), nullable=False)
