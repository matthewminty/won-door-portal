"""add stage to lead

Revision ID: 001_add_stage_to_lead
Revises:
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_stage_to_lead'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leads', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('leads', schema=None) as batch_op:
        batch_op.drop_column('stage')
