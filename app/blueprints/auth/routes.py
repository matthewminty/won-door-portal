"""
Auth Blueprint — Login, Logout, Profile
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, utcnow

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = utcnow()
            session["region"] = user.default_region
            db.session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
        flash("Invalid username or password.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_profile":
            current_user.display_name = request.form.get("display_name", current_user.display_name)
            current_user.email = request.form.get("email", current_user.email)
            current_user.default_region = request.form.get("default_region", current_user.default_region)
            current_user.theme = request.form.get("theme", current_user.theme)
            db.session.commit()
            flash("Profile updated.", "success")
        elif action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New passwords don't match.", "error")
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash("Password changed.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
