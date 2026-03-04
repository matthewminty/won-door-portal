"""Contacts Blueprint — Address book"""
from flask import Blueprint, render_template
from flask_login import login_required

contacts_bp = Blueprint("contacts", __name__)

@contacts_bp.route("/")
@login_required
def index():
    return render_template("contacts/index.html")
