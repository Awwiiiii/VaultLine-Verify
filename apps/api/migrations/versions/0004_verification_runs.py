"""Append-only verification run and finding history."""

import sqlalchemy as sa
from alembic import op

revision = "0004_verification_runs"
down_revision = "0003_financial_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "verification_case_id",
            sa.Uuid(),
            sa.ForeignKey("verification_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rule_set_version", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("tolerances", sa.JSON(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('passed','discrepancy','insufficient_evidence','not_applicable')",
            name="ck_run_outcome",
        ),
    )
    op.create_index(
        "ix_verification_runs_verification_case_id", "verification_runs", ["verification_case_id"]
    )
    op.create_table(
        "verification_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("verification_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('passed','discrepancy','insufficient_evidence','not_applicable')",
            name="ck_finding_outcome",
        ),
    )
    op.create_index("ix_verification_findings_run_id", "verification_findings", ["run_id"])


def downgrade() -> None:
    op.drop_table("verification_findings")
    op.drop_table("verification_runs")
