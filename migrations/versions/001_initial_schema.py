"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('username', sa.String(80), unique=True, nullable=False),
        sa.Column('email', sa.String(120), unique=True, nullable=True),
        sa.Column('display_name', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='standard'),
        sa.Column('default_region', sa.String(10), nullable=False, server_default='au'),
        sa.Column('theme', sa.String(10), nullable=False, server_default='light'),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('last_login', sa.DateTime, nullable=True),
    )

    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('region', sa.String(10), nullable=False, server_default='au'),
        sa.Column('job_number', sa.String(64), unique=True, nullable=False),
        sa.Column('job_name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='Active'),
        sa.Column('job_type', sa.String(30), nullable=True),
        sa.Column('industry', sa.String(64), nullable=True),
        sa.Column('address', sa.String(255), nullable=True),
        sa.Column('territory', sa.String(64), nullable=True),
        sa.Column('nz_sell_price', sa.Float, nullable=True),
        sa.Column('au_sell_price', sa.Float, nullable=True),
        sa.Column('progress_pct', sa.Integer, server_default='0'),
        sa.Column('manufacture_start', sa.Date, nullable=True),
        sa.Column('manufacture_end', sa.Date, nullable=True),
        sa.Column('shipping_start', sa.Date, nullable=True),
        sa.Column('shipping_end', sa.Date, nullable=True),
        sa.Column('installation_start', sa.Date, nullable=True),
        sa.Column('installation_end', sa.Date, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
    )

    op.create_table(
        'leads',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('region', sa.String(10), nullable=False, server_default='au'),
        sa.Column('project_name', sa.String(255), nullable=False),
        sa.Column('client', sa.String(255), nullable=False),
        sa.Column('contact_name', sa.String(128), nullable=True),
        sa.Column('phone', sa.String(64), nullable=True),
        sa.Column('email', sa.String(128), nullable=True),
        sa.Column('brand', sa.String(20), server_default='MPA'),
        sa.Column('status', sa.String(20), nullable=False, server_default='Hot'),
        sa.Column('state', sa.String(20), nullable=True),
        sa.Column('application', sa.String(128), nullable=True),
        sa.Column('lead_source', sa.String(64), nullable=True),
        sa.Column('products', sa.Text, nullable=True),
        sa.Column('value', sa.Float, nullable=False, server_default='0'),
        sa.Column('quote_date', sa.Date, nullable=True),
        sa.Column('last_contact', sa.Date, nullable=True),
        sa.Column('follow_up', sa.Date, nullable=True),
        sa.Column('won_date', sa.Date, nullable=True),
        sa.Column('next_action', sa.Text, nullable=True),
        sa.Column('stage', sa.String(64), nullable=True),
        sa.Column('lost_reason', sa.String(128), nullable=True),
        sa.Column('lost_notes', sa.Text, nullable=True),
        sa.Column('assigned_to', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('jobs.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
    )

    op.create_table(
        'lead_notes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('lead_id', sa.Integer, sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('note_text', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'doors',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('door_number', sa.String(64), nullable=True),
        sa.Column('location', sa.String(128), nullable=True),
        sa.Column('type', sa.String(64), nullable=True),
        sa.Column('configuration', sa.String(64), nullable=True),
        sa.Column('width', sa.Float, nullable=True),
        sa.Column('height', sa.Float, nullable=True),
        sa.Column('door_colour', sa.String(64), nullable=True),
        sa.Column('track_colour', sa.String(64), nullable=True),
        sa.Column('latch_lock', sa.String(16), nullable=True),
        sa.Column('stack', sa.String(32), nullable=True),
        sa.Column('sweep', sa.String(32), nullable=True),
    )

    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('company', sa.String(128), nullable=True),
        sa.Column('position', sa.String(128), nullable=True),
        sa.Column('email', sa.String(128), nullable=True),
        sa.Column('phone', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'contact_links',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('contact_id', sa.Integer, sa.ForeignKey('contacts.id'), nullable=False),
        sa.Column('lead_id', sa.Integer, sa.ForeignKey('leads.id'), nullable=True),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('jobs.id'), nullable=True),
        sa.Column('is_primary', sa.Boolean, server_default=sa.text('false')),
    )

    op.create_table(
        'job_actions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('category', sa.String(128), nullable=True),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('position', sa.Integer, server_default='0'),
        sa.Column('is_required', sa.Boolean, server_default=sa.text('false')),
        sa.Column('checked', sa.Boolean, server_default=sa.text('false')),
        sa.Column('checked_at', sa.DateTime, nullable=True),
        sa.Column('checked_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_na', sa.Boolean, server_default=sa.text('false')),
    )

    op.create_table(
        'job_notes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('note_text', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'action_templates',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('category', sa.String(128), nullable=False),
        sa.Column('items', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'activity_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('region', sa.String(10), nullable=True),
        sa.Column('entity_type', sa.String(20), nullable=True),
        sa.Column('entity_id', sa.Integer, nullable=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table('activity_log')
    op.drop_table('action_templates')
    op.drop_table('job_notes')
    op.drop_table('job_actions')
    op.drop_table('contact_links')
    op.drop_table('contacts')
    op.drop_table('doors')
    op.drop_table('lead_notes')
    op.drop_table('leads')
    op.drop_table('jobs')
    op.drop_table('users')
