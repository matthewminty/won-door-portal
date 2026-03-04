"""picklist items table

Revision ID: 002_picklist
Revises: 001_initial_schema
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "002_picklist"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None

_APPLICATIONS = [
    "Aged Care", "Commercial", "Community Centre", "Convention/Events",
    "Early Childcare", "Education", "Government", "Healthcare",
    "Offices/Meeting Rooms", "Religious", "Shopping Centre", "Sports Club", "Other",
]
_LEAD_SOURCES = [
    "Specified", "Website", "Referral", "Architect",
    "Builder", "Repeat Client", "Cold Outreach", "Trade Show", "Other",
]
_LOST_REASONS = [
    "Price", "Competitor", "Project Cancelled", "No Decision", "Timing", "Other",
]
_PRODUCTS = [
    ("DuraFlex", False),
    ("DuraSound", False),
    ("FireGuard", True),
    ("Moveable Fire Wall", True),
    ("Operable Wall", False),
]
_STAGES = ["Concept", "Design", "Tender"]


def upgrade():
    t = op.create_table(
        "picklist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("value", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_fire", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "value", name="uq_picklist_cat_val"),
    )
    op.create_index("ix_picklist_category", "picklist_items", ["category"])

    rows = []
    for i, v in enumerate(_APPLICATIONS):
        rows.append({"category": "application", "value": v, "sort_order": i, "is_fire": False})
    for i, v in enumerate(_LEAD_SOURCES):
        rows.append({"category": "lead_source", "value": v, "sort_order": i, "is_fire": False})
    for i, v in enumerate(_LOST_REASONS):
        rows.append({"category": "lost_reason", "value": v, "sort_order": i, "is_fire": False})
    for i, (v, fire) in enumerate(_PRODUCTS):
        rows.append({"category": "product", "value": v, "sort_order": i, "is_fire": fire})
    for i, v in enumerate(_STAGES):
        rows.append({"category": "stage", "value": v, "sort_order": i, "is_fire": False})

    op.bulk_insert(t, rows)


def downgrade():
    op.drop_index("ix_picklist_category", "picklist_items")
    op.drop_table("picklist_items")
