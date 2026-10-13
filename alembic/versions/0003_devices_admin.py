"""Add admin flag and push-notification device tokens.

Revision ID: 0003_devices_admin
Revises: 0002_firebase_auth
Create Date: 2026-10-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_devices_admin"
down_revision: Union[str, Sequence[str], None] = "0002_firebase_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLATFORM_VALUES = ("ios", "android", "web")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    device_platform = postgresql.ENUM(*PLATFORM_VALUES, name="device_platform", create_type=False)
    device_platform.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "user_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", device_platform, nullable=False),
        sa.Column("device_name", sa.String(length=120), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("token", name="uq_user_devices_token"),
    )
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
    op.create_index("ix_user_devices_created_at", "user_devices", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_user_devices_created_at", table_name="user_devices")
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_table("user_devices")
    postgresql.ENUM(name="device_platform").drop(op.get_bind(), checkfirst=True)
    op.drop_column("users", "is_admin")
