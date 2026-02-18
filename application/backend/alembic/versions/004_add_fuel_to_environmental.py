"""Add fuel fields to environmental_data

Revision ID: 004
Revises: 003
Create Date: 2026-02-17 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add fuel estimation fields to environmental_data table
    op.add_column('environmental_data', sa.Column('one_hour_fuel', sa.DECIMAL(10, 4), nullable=True))
    op.add_column('environmental_data', sa.Column('ten_hour_fuel', sa.DECIMAL(10, 4), nullable=True))
    op.add_column('environmental_data', sa.Column('hundred_hour_fuel', sa.DECIMAL(10, 4), nullable=True))


def downgrade() -> None:
    # Remove fuel estimation fields
    op.drop_column('environmental_data', 'hundred_hour_fuel')
    op.drop_column('environmental_data', 'ten_hour_fuel')
    op.drop_column('environmental_data', 'one_hour_fuel')
