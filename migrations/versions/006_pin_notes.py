"""add is_pinned to lead_notes and job_notes

Revision ID: 006_pin_notes
Revises: 005_note_edit_tracking
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lead_notes") as batch_op:
        batch_op.add_column(sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="0"))
    with op.batch_alter_table("job_notes") as batch_op:
        batch_op.add_column(sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("lead_notes") as batch_op:
        batch_op.drop_column("is_pinned")
    with op.batch_alter_table("job_notes") as batch_op:
        batch_op.drop_column("is_pinned")
