"""
Won-Door Portal — Database Models
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ═══════════════════════════════════════════════════════════
# USER
# ═══════════════════════════════════════════════════════════
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="standard")  # admin | standard
    default_region = db.Column(db.String(10), nullable=False, default="au")  # au | nz
    theme = db.Column(db.String(10), nullable=False, default="light")  # light | dark
    avatar_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.username}>"


# ═══════════════════════════════════════════════════════════
# LEAD (Pipeline)
# ═══════════════════════════════════════════════════════════
class Lead(db.Model):
    __tablename__ = "leads"
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(10), nullable=False, default="au")  # au | nz

    # Core
    project_name = db.Column(db.String(255), nullable=False)
    client = db.Column(db.String(255), nullable=False)
    contact_name = db.Column(db.String(128))
    phone = db.Column(db.String(64))
    email = db.Column(db.String(128))

    # Classification
    brand = db.Column(db.String(20), default="MPA")  # MPA | Won-Door
    status = db.Column(db.String(20), nullable=False, default="Hot")  # Hot | Long Burn | Won | Lost | Dead
    state = db.Column(db.String(20))  # NSW, VIC, QLD, etc.
    application = db.Column(db.String(128))  # Education, Commercial, etc.
    lead_source = db.Column(db.String(64))  # Specified, Website, Referral, etc.

    # Products (stored as comma-separated)
    products = db.Column(db.Text)  # "DuraSound,Operable Wall"

    # Value & dates
    value = db.Column(db.Float, nullable=False, default=0)
    quote_date = db.Column(db.Date, nullable=True)
    last_contact = db.Column(db.Date, nullable=True)
    follow_up = db.Column(db.Date, nullable=True)
    won_date = db.Column(db.Date, nullable=True)
    next_action = db.Column(db.Text)

    # Stage (Concept / Design / Tender)
    stage = db.Column(db.String(64), nullable=True)

    # Lost details
    lost_reason = db.Column(db.String(128))
    lost_notes = db.Column(db.Text)

    # Assignment
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_user = db.relationship("User", foreign_keys=[assigned_to])

    # Link to job (when converted)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True)

    # Meta
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Relationships
    notes = db.relationship("LeadNote", backref="lead", cascade="all, delete-orphan", lazy="dynamic")

    def get_products_list(self):
        if not self.products:
            return []
        return [p.strip() for p in self.products.split(",") if p.strip()]

    def set_products_list(self, product_list):
        self.products = ",".join(product_list) if product_list else ""

    def __repr__(self):
        return f"<Lead {self.project_name}>"


class LeadNote(db.Model):
    __tablename__ = "lead_notes"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    note_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_contact_log = db.Column(db.Boolean, default=False, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    editor = db.relationship("User", foreign_keys=[updated_by])


# ═══════════════════════════════════════════════════════════
# JOB
# ═══════════════════════════════════════════════════════════
class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(10), nullable=False, default="au")

    job_number = db.Column(db.String(64), unique=True, nullable=False)
    job_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Active")  # Active | On Hold | Complete
    job_type = db.Column(db.String(30))  # Supply & Install | Supply Only
    industry = db.Column(db.String(64))
    address = db.Column(db.String(255))
    territory = db.Column(db.String(64))

    # Finance
    nz_sell_price = db.Column(db.Float)
    au_sell_price = db.Column(db.Float)
    progress_pct = db.Column(db.Integer, default=0)

    # Key dates
    manufacture_start = db.Column(db.Date)
    manufacture_end = db.Column(db.Date)
    shipping_start = db.Column(db.Date)
    shipping_end = db.Column(db.Date)
    installation_start = db.Column(db.Date)
    installation_end = db.Column(db.Date)

    # Meta
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Relationships
    doors = db.relationship("Door", backref="job", cascade="all, delete-orphan", lazy=True)
    job_notes = db.relationship("JobNote", backref="job", cascade="all, delete-orphan", lazy="dynamic")
    actions = db.relationship("JobAction", backref="job", cascade="all, delete-orphan", lazy=True)
    lead = db.relationship("Lead", backref="linked_job", foreign_keys="Lead.job_id", uselist=False)

    def __repr__(self):
        return f"<Job {self.job_number} {self.job_name}>"


# ═══════════════════════════════════════════════════════════
# DOOR
# ═══════════════════════════════════════════════════════════
class Door(db.Model):
    __tablename__ = "doors"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)

    door_number = db.Column(db.String(64))
    location = db.Column(db.String(128))
    type = db.Column(db.String(64))
    configuration = db.Column(db.String(64))
    width = db.Column(db.Float)
    height = db.Column(db.Float)
    door_colour = db.Column(db.String(64))
    track_colour = db.Column(db.String(64))
    latch_lock = db.Column(db.String(16))  # Latch | Lock
    stack = db.Column(db.String(32))
    sweep = db.Column(db.String(32))


# ═══════════════════════════════════════════════════════════
# COMPANY (Address Book)
# ═══════════════════════════════════════════════════════════
class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(64))
    email = db.Column(db.String(128))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self):
        return f"<Company {self.name}>"


# ═══════════════════════════════════════════════════════════
# CONTACT (Address Book)
# ═══════════════════════════════════════════════════════════
class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(128), nullable=True)
    last_name = db.Column(db.String(128), nullable=True)
    name = db.Column(db.String(128), nullable=False)  # display name = first + last
    company = db.Column(db.String(128))               # legacy text field
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    position = db.Column(db.String(128))
    email = db.Column(db.String(128), index=True)
    phone = db.Column(db.String(64))
    address = db.Column(db.String(255))
    region = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    linked_company = db.relationship("Company", backref="contacts")


# Contact ↔ Lead/Job link table (polymorphic)
class ContactLink(db.Model):
    __tablename__ = "contact_links"
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True)
    is_primary = db.Column(db.Boolean, default=False)

    contact = db.relationship("Contact", backref="links")


# ═══════════════════════════════════════════════════════════
# JOB ACTIONS (Checklists)
# ═══════════════════════════════════════════════════════════
class JobAction(db.Model):
    __tablename__ = "job_actions"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)

    category = db.Column(db.String(128))  # "Manufacturing", "Shipping", "Installation"
    label = db.Column(db.String(255), nullable=False)
    position = db.Column(db.Integer, default=0)
    is_required = db.Column(db.Boolean, default=False)

    checked = db.Column(db.Boolean, default=False)
    checked_at = db.Column(db.DateTime, nullable=True)
    checked_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_na = db.Column(db.Boolean, default=False)

    checker = db.relationship("User", foreign_keys=[checked_by])


class JobNote(db.Model):
    __tablename__ = "job_notes"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    note_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])


# ═══════════════════════════════════════════════════════════
# ACTION TEMPLATES
# ═══════════════════════════════════════════════════════════
class ActionTemplate(db.Model):
    __tablename__ = "action_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)  # "Manufacturing Checklist"
    category = db.Column(db.String(128), nullable=False)
    items = db.Column(db.Text, nullable=False)  # JSON array of {label, is_required, position}
    created_at = db.Column(db.DateTime, default=utcnow)


# ═══════════════════════════════════════════════════════════
# PICKLIST ITEMS (managed via Settings)
# ═══════════════════════════════════════════════════════════
class PicklistItem(db.Model):
    __tablename__ = "picklist_items"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    # categories: application | lead_source | lost_reason | product | stage
    value = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_fire = db.Column(db.Boolean, nullable=False, default=False)  # products only

    __table_args__ = (
        db.UniqueConstraint("category", "value", name="uq_picklist_cat_val"),
    )

    def __repr__(self):
        return f"<PicklistItem {self.category}:{self.value}>"


# ═══════════════════════════════════════════════════════════
# ACTIVITY LOG
# ═══════════════════════════════════════════════════════════
class ActivityLog(db.Model):
    __tablename__ = "activity_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    region = db.Column(db.String(10))
    entity_type = db.Column(db.String(20))  # "lead" | "job" | "contact"
    entity_id = db.Column(db.Integer)
    action = db.Column(db.String(64), nullable=False)  # "created", "updated", "status_changed", etc.
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
