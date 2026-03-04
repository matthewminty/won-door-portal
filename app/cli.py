"""
Won-Door Portal — CLI Commands
"""
import json
import click
from datetime import datetime, date
from flask.cli import with_appcontext
from app import db
from app.models import User, Lead, LeadNote


def register_commands(app):

    @app.cli.command("seed")
    @with_appcontext
    def seed():
        """Create default admin and standard users."""
        if User.query.filter_by(username="matt").first():
            click.echo("Users already exist, skipping seed.")
            return

        admin = User(
            username="matt",
            email="matt@won-door.com.au",
            display_name="Matt",
            role="admin",
            default_region="au",
        )
        admin.set_password("changeme123")

        partner = User(
            username="partner",
            email="partner@won-door.co.nz",
            display_name="Partner",
            role="standard",
            default_region="nz",
        )
        partner.set_password("changeme123")

        db.session.add_all([admin, partner])
        db.session.commit()
        click.echo("Seeded 2 users: matt (admin/AU), partner (standard/NZ)")
        click.echo("Default password for both: changeme123")
        click.echo("CHANGE THESE IMMEDIATELY after first login!")

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    @click.option("--email", default=None)
    @click.option("--name", default=None)
    @with_appcontext
    def create_admin(username, password, email, name):
        """Create a new admin user."""
        if User.query.filter_by(username=username).first():
            click.echo(f"User '{username}' already exists.")
            return

        user = User(
            username=username,
            email=email,
            display_name=name or username,
            role="admin",
            default_region="au",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{username}' created.")

    @app.cli.command("import-leads")
    @click.argument("filepath", default="mpa-backup-2026-03-04.json")
    @click.option("--region", default="au", help="Region to tag all leads (au|nz)")
    @click.option("--clear", is_flag=True, default=False, help="Delete existing leads before import")
    @with_appcontext
    def import_leads(filepath, region, clear):
        """Import leads from an MPA Lead Tracker JSON backup file."""

        def parse_date(val):
            if not val:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(val, fmt).date()
                except (ValueError, TypeError):
                    pass
            return None

        import os
        if not os.path.exists(filepath):
            click.echo(f"No import file found at {filepath}, skipping.")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            click.echo(f"ERROR: Invalid JSON — {e}", err=True)
            return

        raw_leads = data.get("leads", data if isinstance(data, list) else [])
        click.echo(f"Found {len(raw_leads)} leads in {filepath}")

        if clear:
            deleted = Lead.query.count()
            LeadNote.query.delete()
            Lead.query.delete()
            db.session.commit()
            click.echo(f"Cleared {deleted} existing leads.")

        # Build a display_name -> User map for rep assignment
        users = {u.display_name.lower(): u for u in User.query.all()}
        users.update({u.username.lower(): u for u in User.query.all()})

        created = skipped = notes_added = 0

        for raw in raw_leads:
            project_name = (raw.get("name") or "").strip()
            client = (raw.get("client") or "").strip()

            if not project_name:
                skipped += 1
                continue

            # Products: may be list or comma string
            raw_products = raw.get("products", "")
            if isinstance(raw_products, list):
                products_str = ",".join(p for p in raw_products if p)
            else:
                products_str = raw_products or ""

            # Rep -> assigned_to user id
            rep_name = (raw.get("rep") or "").strip().lower()
            assigned_user = users.get(rep_name)

            # Parse created_at
            created_raw = raw.get("created") or raw.get("created_at")
            try:
                created_at = datetime.fromisoformat(created_raw) if created_raw else datetime.utcnow()
            except (ValueError, TypeError):
                created_at = datetime.utcnow()

            lead = Lead(
                region=region,
                project_name=project_name,
                client=client or project_name,
                contact_name=raw.get("contact") or None,
                phone=raw.get("phone") or None,
                email=raw.get("email") or None,
                brand=raw.get("brand") or "MPA",
                status=raw.get("status") or "Hot",
                state=raw.get("state") or None,
                application=raw.get("application") or None,
                lead_source=raw.get("leadsource") or None,
                products=products_str or None,
                value=float(raw.get("value") or 0),
                quote_date=parse_date(raw.get("quotedate")),
                last_contact=parse_date(raw.get("lastcontact")),
                follow_up=parse_date(raw.get("followup")),
                won_date=parse_date(raw.get("wondate")),
                next_action=raw.get("nextaction") or None,
                stage=raw.get("stage") or None,
                lost_reason=raw.get("lostReason") or None,
                lost_notes=raw.get("lostNotes") or None,
                assigned_to=assigned_user.id if assigned_user else None,
                created_at=created_at,
                updated_at=created_at,
            )
            db.session.add(lead)
            db.session.flush()  # get lead.id for notes

            # Import notes
            raw_notes = raw.get("notes", [])
            if isinstance(raw_notes, list):
                for n in raw_notes:
                    if isinstance(n, dict):
                        text = n.get("text") or n.get("note") or ""
                        note_date_raw = n.get("date") or n.get("created")
                        try:
                            note_date = datetime.fromisoformat(note_date_raw) if note_date_raw else created_at
                        except (ValueError, TypeError):
                            note_date = created_at
                        note_rep = (n.get("rep") or "").strip().lower()
                        note_user = users.get(note_rep)
                    else:
                        text = str(n)
                        note_date = created_at
                        note_user = assigned_user
                    if text.strip():
                        db.session.add(LeadNote(
                            lead_id=lead.id,
                            user_id=note_user.id if note_user else None,
                            note_text=text.strip(),
                            created_at=note_date,
                        ))
                        notes_added += 1
            elif isinstance(raw_notes, str) and raw_notes.strip():
                db.session.add(LeadNote(
                    lead_id=lead.id,
                    user_id=assigned_user.id if assigned_user else None,
                    note_text=raw_notes.strip(),
                    created_at=created_at,
                ))
                notes_added += 1

            created += 1

        db.session.commit()
        click.echo(f"Imported {created} leads, {notes_added} notes. Skipped {skipped}.")
