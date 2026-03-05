"""add companies table and extend contacts

Revision ID: 004_company_contact
Revises: 003_note_types
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "004_company_contact"
down_revision = "003_note_types"
branch_labels = None
depends_on = None


def upgrade():
    # Create companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("email", sa.String(128), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Extend contacts table
    op.add_column("contacts", sa.Column("first_name", sa.String(128), nullable=True))
    op.add_column("contacts", sa.Column("last_name", sa.String(128), nullable=True))
    op.add_column("contacts", sa.Column("address", sa.String(255), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
    )


def downgrade():
    op.drop_column("contacts", "company_id")
    op.drop_column("contacts", "address")
    op.drop_column("contacts", "last_name")
    op.drop_column("contacts", "first_name")
    op.drop_table("companies")
