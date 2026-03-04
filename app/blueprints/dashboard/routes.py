"""Dashboard Blueprint — Landing page"""
from flask import Blueprint, render_template, session
from flask_login import login_required

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def index():
    region = session.get("region", "all")
    return render_template("dashboard/index.html", region=region)
