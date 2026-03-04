"""
Won-Door Portal — CLI Commands
"""
import click
from flask.cli import with_appcontext
from app import db
from app.models import User


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
