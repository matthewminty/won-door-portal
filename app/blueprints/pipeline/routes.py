"""Pipeline Blueprint — Lead tracking"""
from flask import Blueprint, render_template, session
from flask_login import login_required

pipeline_bp = Blueprint("pipeline", __name__)

@pipeline_bp.route("/")
@login_required
def index():
    region = session.get("region", "all")
    return render_template("pipeline/index.html", region=region)
