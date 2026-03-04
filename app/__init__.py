"""
Won-Door Portal — App Factory
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


def create_app(config_name=None):
    app = Flask(__name__)

    # ── Config ──
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # ── Database URL (try all names Railway may use) ──
    _db_url = (
        os.environ.get("DATABASE_URL") or
        os.environ.get("POSTGRES_URL") or
        os.environ.get("POSTGRESQL_URL") or
        "sqlite:///portal.db"
    )
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
    print(f"[DB] Connecting to: {_db_url[:35]}...", flush=True)

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    # ── Init extensions ──
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # ── User loader ──
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Context processors ──
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from flask import session

        region = session.get("region", "all")
        return dict(
            active_region=region,
            regions=["au", "nz", "all"],
        )

    # ── Register blueprints ──
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.pipeline.routes import pipeline_bp
    from app.blueprints.jobs.routes import jobs_bp
    from app.blueprints.contacts.routes import contacts_bp
    from app.blueprints.settings.routes import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pipeline_bp, url_prefix="/pipeline")
    app.register_blueprint(jobs_bp, url_prefix="/jobs")
    app.register_blueprint(contacts_bp, url_prefix="/contacts")
    app.register_blueprint(settings_bp)

    # ── Region switcher route ──
    from flask import request, session, redirect

    @app.route("/set-region/<region>")
    def set_region(region):
        if region in ("au", "nz", "all"):
            session["region"] = region
        return redirect(request.referrer or "/")

    # ── CLI commands ──
    from app.cli import register_commands

    register_commands(app)

    # ── Theme toggle API ──
    @app.route("/api/theme", methods=["POST"])
    def api_theme():
        from flask_login import current_user as cu
        from flask import jsonify

        if cu.is_authenticated:
            data = request.get_json(silent=True) or {}
            theme = data.get("theme", "light")
            if theme in ("light", "dark"):
                cu.theme = theme
                db.session.commit()
        return jsonify({"ok": True})

    return app
