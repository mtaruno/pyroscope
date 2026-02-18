"""Add fuel estimation fields

Revision ID: 003
Revises: 002
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Drop the old fuel_load column (String type - contains "Low", "Medium", "High")
    op.drop_column('scan_records', 'fuel_load')
    
    # Step 2: Add new fuel_load column as DECIMAL
    op.add_column('scan_records', sa.Column('fuel_load', sa.DECIMAL(10, 4), nullable=True))
    
    # Step 3: Add new fuel estimation fields
    op.add_column('scan_records', sa.Column('one_hour_fuel', sa.DECIMAL(10, 4), nullable=True))
    op.add_column('scan_records', sa.Column('ten_hour_fuel', sa.DECIMAL(10, 4), nullable=True))
    op.add_column('scan_records', sa.Column('hundred_hour_fuel', sa.DECIMAL(10, 4), nullable=True))
    op.add_column('scan_records', sa.Column('pine_cone_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove new fuel estimation fields
    op.drop_column('scan_records', 'pine_cone_count')
    op.drop_column('scan_records', 'hundred_hour_fuel')
    op.drop_column('scan_records', 'ten_hour_fuel')
    op.drop_column('scan_records', 'one_hour_fuel')
    
    # Remove new fuel_load DECIMAL column
    op.drop_column('scan_records', 'fuel_load')
    
    # Add back old fuel_load column as String
    op.add_column('scan_records', sa.Column('fuel_load', sa.String(20), nullable=True))
