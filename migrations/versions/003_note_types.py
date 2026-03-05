"""add is_contact_log to lead_notes

Revision ID: 003_note_types
Revises: 002_picklist
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "003_note_types"
down_revision = "002_picklist"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lead_notes",
        sa.Column("is_contact_log", sa.Boolean(), nullable=True, server_default=sa.text("false")),
    )


def downgrade():
    op.drop_column("lead_notes", "is_contact_log")
