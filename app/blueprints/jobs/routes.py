"""Jobs Blueprint — Job management"""
from flask import Blueprint, render_template, session
from flask_login import login_required

jobs_bp = Blueprint("jobs", __name__)

@jobs_bp.route("/")
@login_required
def index():
    region = session.get("region", "all")
    return render_template("jobs/index.html", region=region)
