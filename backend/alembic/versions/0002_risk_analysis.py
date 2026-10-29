"""add risk_analysis to policy_snapshots

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive and nullable: existing snapshots keep working with no risk data.
    op.add_column(
        "policy_snapshots",
        sa.Column("risk_analysis", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                  nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("policy_snapshots") as batch:
        batch.drop_column("risk_analysis")
