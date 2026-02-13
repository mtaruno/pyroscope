"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-02-07 18:47:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
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
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create scan_records table
    op.create_table(
        'scan_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('zone_id', sa.String(length=50), nullable=False),
        sa.Column('zone_name', sa.String(length=100), nullable=False),
        sa.Column('latitude', sa.DECIMAL(precision=10, scale=8), nullable=False),
        sa.Column('longitude', sa.DECIMAL(precision=11, scale=8), nullable=False),
        sa.Column('gps_accuracy', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('scan_area', sa.String(length=50), nullable=True),
        sa.Column('duration', sa.String(length=50), nullable=True),
        sa.Column('risk_level', sa.Enum('low', 'medium', 'high', name='risklevel'), nullable=True),
        sa.Column('avg_plant_temp', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('avg_air_temp', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('avg_humidity', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('wind_speed', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('temp_diff', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('fuel_load', sa.String(length=20), nullable=True),
        sa.Column('fuel_density', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('biomass', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('robot_id', sa.String(length=50), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_location', 'scan_records', ['latitude', 'longitude'])
    op.create_index('idx_completed_at', 'scan_records', ['completed_at'])
    op.create_index('idx_risk_level', 'scan_records', ['risk_level'])
    
    # Create environmental_data table
    op.create_table(
        'environmental_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('air_temperature', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('air_humidity', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('wind_speed', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('plant_temperature', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('latitude', sa.DECIMAL(precision=10, scale=8), nullable=True),
        sa.Column('longitude', sa.DECIMAL(precision=11, scale=8), nullable=True),
        sa.Column('measured_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scan_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_scan_measured', 'environmental_data', ['scan_id', 'measured_at'])
    
    # Create scan_images table
    op.create_table(
        'scan_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('image_type', sa.Enum('thermal', 'visible', 'panorama', 'detail', name='imagetype'), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=50), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('latitude', sa.DECIMAL(precision=10, scale=8), nullable=True),
        sa.Column('longitude', sa.DECIMAL(precision=11, scale=8), nullable=True),
        sa.Column('captured_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scan_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_scan_type', 'scan_images', ['scan_id', 'image_type'])
    
    # Create robot_status table
    op.create_table(
        'robot_status',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('robot_id', sa.String(length=50), nullable=False),
        sa.Column('battery_level', sa.Integer(), nullable=True),
        sa.Column('storage_used', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('storage_total', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('signal_strength', sa.String(length=20), nullable=True),
        sa.Column('operating_state', sa.Enum('idle', 'scanning', 'charging', 'error', name='operatingstate'), nullable=True),
        sa.Column('latitude', sa.DECIMAL(precision=10, scale=8), nullable=True),
        sa.Column('longitude', sa.DECIMAL(precision=11, scale=8), nullable=True),
        sa.Column('recorded_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_robot_time', 'robot_status', ['robot_id', 'recorded_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_robot_time', table_name='robot_status')
    op.drop_table('robot_status')
    
    op.drop_index('idx_scan_type', table_name='scan_images')
    op.drop_table('scan_images')
    
    op.drop_index('idx_scan_measured', table_name='environmental_data')
    op.drop_table('environmental_data')
    
    op.drop_index('idx_risk_level', table_name='scan_records')
    op.drop_index('idx_completed_at', table_name='scan_records')
    op.drop_index('idx_location', table_name='scan_records')
    op.drop_table('scan_records')
    
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
