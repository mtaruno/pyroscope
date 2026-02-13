"""Simplify schema - remove users table and zone_name

Revision ID: 002
Revises: 001
Create Date: 2026-02-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove foreign key constraint from scan_records
    op.drop_constraint('scan_records_ibfk_1', 'scan_records', type_='foreignkey')
    
    # Drop user_id column from scan_records
    op.drop_column('scan_records', 'user_id')
    
    # Drop zone_name column from scan_records
    op.drop_column('scan_records', 'zone_name')
    
    # Drop users table
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')


def downgrade() -> None:
    # Recreate users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('robot_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    
    # Add back zone_name column
    op.add_column('scan_records', sa.Column('zone_name', sa.String(length=100), nullable=True))
    
    # Add back user_id column
    op.add_column('scan_records', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Add back foreign key
    op.create_foreign_key('scan_records_ibfk_1', 'scan_records', 'users', ['user_id'], ['id'])
