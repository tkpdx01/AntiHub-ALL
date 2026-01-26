"""add_zai_tts_accounts_and_usage_fields

Revision ID: f7a8b9c0d1e2
Revises: f1b2c3d4e5f6
Create Date: 2026-01-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "f1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zai_tts_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Integer(), server_default="1", nullable=False),
        sa.Column("zai_user_id", sa.String(length=128), nullable=False),
        sa.Column("voice_id", sa.String(length=128), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_zai_tts_accounts_user_id"), "zai_tts_accounts", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_zai_tts_accounts_status"), "zai_tts_accounts", ["status"], unique=False
    )

    op.add_column("usage_logs", sa.Column("tts_voice_id", sa.String(length=128), nullable=True))
    op.add_column("usage_logs", sa.Column("tts_account_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("usage_logs", "tts_account_id")
    op.drop_column("usage_logs", "tts_voice_id")
    op.drop_index(op.f("ix_zai_tts_accounts_status"), table_name="zai_tts_accounts")
    op.drop_index(op.f("ix_zai_tts_accounts_user_id"), table_name="zai_tts_accounts")
    op.drop_table("zai_tts_accounts")
