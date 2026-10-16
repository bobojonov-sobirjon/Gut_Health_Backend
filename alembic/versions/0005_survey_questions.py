"""Dynamic onboarding questions and per-user answers.

Revision ID: 0005_survey_questions
Revises: 0004_day_status_factors
Create Date: 2026-10-15

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_survey_questions"
down_revision: Union[str, Sequence[str], None] = "0004_day_status_factors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KIND = postgresql.ENUM("single", "multi", "tiles", "text", name="survey_question_kind")
KIND_COLUMN = postgresql.ENUM(
    "single",
    "multi",
    "tiles",
    "text",
    name="survey_question_kind",
    create_type=False,
)


def upgrade() -> None:
    KIND.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "survey_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("placeholder", sa.String(300), nullable=True),
        sa.Column("kind", KIND_COLUMN, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_skip", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_survey_questions_sort_order", "survey_questions", ["sort_order"])
    op.create_table(
        "survey_options",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("survey_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("emoji", sa.String(16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("clears_others", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("question_id", "label", name="uq_survey_options_question_label"),
    )
    op.create_index("ix_survey_options_question_id", "survey_options", ["question_id"])
    op.create_table(
        "survey_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("survey_questions.id", ondelete="SET NULL")),
        sa.Column("option_id", sa.Uuid(), sa.ForeignKey("survey_options.id", ondelete="SET NULL")),
        sa.Column("question_title", sa.String(200), nullable=False),
        sa.Column("question_kind", sa.String(20), nullable=False),
        sa.Column("value_text", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_survey_answers_user_id", "survey_answers", ["user_id"])
    _seed()


def _seed() -> None:
    options = sa.table(
        "survey_options",
        sa.column("id", sa.Uuid()),
        sa.column("question_id", sa.Uuid()),
        sa.column("label", sa.String()),
        sa.column("emoji", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("clears_others", sa.Boolean()),
    )
    goal = uuid.UUID("11111111-1111-4111-8111-111111111101")
    concern = uuid.UUID("11111111-1111-4111-8111-111111111102")
    track = uuid.UUID("11111111-1111-4111-8111-111111111103")
    journey = uuid.UUID("11111111-1111-4111-8111-111111111104")
    question_rows = [
            {
                "id": goal,
                "title": "What would you like to understand better?",
                "subtitle": None,
                "placeholder": None,
                "kind": "single",
                "sort_order": 1,
                "is_active": True,
                "is_required": True,
                "allow_skip": False,
            },
            {
                "id": concern,
                "title": "Any specific concerns?",
                "subtitle": "(Select all that apply)",
                "placeholder": None,
                "kind": "multi",
                "sort_order": 2,
                "is_active": True,
                "is_required": False,
                "allow_skip": True,
            },
            {
                "id": track,
                "title": "What would you like to track?",
                "subtitle": None,
                "placeholder": None,
                "kind": "tiles",
                "sort_order": 3,
                "is_active": True,
                "is_required": False,
                "allow_skip": True,
            },
            {
                "id": journey,
                "title": "Let's start your 30-day journey",
                "subtitle": "Track your daily bowel movements\nLog food, drinks and lifestyle factors\nDiscover patterns and get AI insights",
                "placeholder": "Track consistently for 30 days",
                "kind": "text",
                "sort_order": 4,
                "is_active": True,
                "is_required": False,
                "allow_skip": False,
            },
        ]
    insert_question = sa.text(
        """
        INSERT INTO survey_questions
            (id, title, subtitle, placeholder, kind, sort_order, is_active, is_required, allow_skip)
        VALUES
            (:id, :title, :subtitle, :placeholder, CAST(:kind AS survey_question_kind),
             :sort_order, :is_active, :is_required, :allow_skip)
        """
    )
    for row in question_rows:
        op.get_bind().execute(insert_question, row)
    goal_labels = [
        "My bowel regularity",
        "How my stool changes",
        "Patterns between food and digestion",
        "I just want to keep a diary",
    ]
    concern_labels = [
        ("Infrequent bowel movements", False),
        ("Loose stools", False),
        ("Pain or discomfort", False),
        ("Bloating", False),
        ("I'm not sure yet", True),
    ]
    tiles = [
        ("Coffee", "☕"),
        ("Dairy", "🥛"),
        ("Alcohol", "🍹"),
        ("Beans & legumes", "🫘"),
        ("Spicy food", "🌶️"),
        ("Water intake", "💧"),
        ("Stress", "🧁"),
        ("Sleep", "🌙"),
    ]
    rows: list[dict[str, object]] = []
    for index, label in enumerate(goal_labels, start=1):
        rows.append(_option(uuid.UUID(f"11111111-1111-4111-8111-1111111111{index:02d}"), goal, label, None, index, False))
    for index, (label, exclusive) in enumerate(concern_labels, start=1):
        rows.append(
            _option(uuid.UUID(f"11111111-1111-4111-8111-1111111121{index:02d}"), concern, label, None, index, exclusive)
        )
    for index, (label, emoji) in enumerate(tiles, start=1):
        rows.append(_option(uuid.UUID(f"11111111-1111-4111-8111-1111111131{index:02d}"), track, label, emoji, index, False))
    op.bulk_insert(options, rows)


def _option(
    option_id: uuid.UUID,
    question_id: uuid.UUID,
    label: str,
    emoji: str | None,
    sort_order: int,
    clears_others: bool,
) -> dict[str, object]:
    return {
        "id": option_id,
        "question_id": question_id,
        "label": label,
        "emoji": emoji,
        "sort_order": sort_order,
        "is_active": True,
        "clears_others": clears_others,
    }


def downgrade() -> None:
    op.drop_index("ix_survey_answers_user_id", table_name="survey_answers")
    op.drop_table("survey_answers")
    op.drop_index("ix_survey_options_question_id", table_name="survey_options")
    op.drop_table("survey_options")
    op.drop_index("ix_survey_questions_sort_order", table_name="survey_questions")
    op.drop_table("survey_questions")
    KIND.drop(op.get_bind(), checkfirst=True)
