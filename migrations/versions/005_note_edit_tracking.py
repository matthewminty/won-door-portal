"""Add updated_at/updated_by to lead_notes; add region to contacts

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    # Note edit tracking
    op.add_column("lead_notes", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("lead_notes", sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    # Contact region
    op.add_column("contacts", sa.Column("region", sa.String(128), nullable=True))


def downgrade():
    op.drop_column("lead_notes", "updated_at")
    op.drop_column("lead_notes", "updated_by")
    op.drop_column("contacts", "region")
