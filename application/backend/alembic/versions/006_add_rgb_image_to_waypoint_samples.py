"""Add rgb_image_id to scan_waypoint_samples for RealSense D435i per-waypoint image.

Revision ID: 006
Revises: 005
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "scan_waypoint_samples",
        sa.Column(
            "rgb_image_id",
            sa.Integer(),
            sa.ForeignKey("scan_images.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_waypoint_rgb_image",
        "scan_waypoint_samples",
        ["rgb_image_id"],
    )


def downgrade():
    op.drop_index("idx_waypoint_rgb_image", table_name="scan_waypoint_samples")
    op.drop_column("scan_waypoint_samples", "rgb_image_id")
