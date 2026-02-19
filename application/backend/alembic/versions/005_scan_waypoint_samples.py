"""Add scan_waypoint_samples table

Revision ID: 005
Revises: 004
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_waypoint_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("air_temperature", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("air_humidity", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("thermal_mean", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["scan_id"], ["scan_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_waypoint_scan_seq", "scan_waypoint_samples", ["scan_id", "sequence_index"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_waypoint_scan_seq", table_name="scan_waypoint_samples")
    op.drop_table("scan_waypoint_samples")
