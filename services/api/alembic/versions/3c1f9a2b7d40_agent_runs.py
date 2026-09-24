"""agent_runs

Revision ID: 3c1f9a2b7d40
Revises: 0ef99343d0c9
Create Date: 2026-09-24 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c1f9a2b7d40"
down_revision: str | Sequence[str] | None = "0ef99343d0c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_version_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("engine", sa.JSON(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_organization_id"), "agent_runs", ["organization_id"])
    op.create_index(op.f("ix_agent_runs_user_id"), "agent_runs", ["user_id"])
    op.create_index(op.f("ix_agent_runs_dataset_version_id"), "agent_runs", ["dataset_version_id"])
    op.create_index(op.f("ix_agent_runs_thread_id"), "agent_runs", ["thread_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_runs_thread_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_dataset_version_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_user_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_organization_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
