"""Settings Blueprint — Admin-only picklist management"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db
from app.models import PicklistItem

settings_bp = Blueprint("settings", __name__)

CATEGORY_LABELS = {
    "application": "Applications",
    "lead_source": "Lead Sources",
    "lost_reason": "Lost Reasons",
    "product": "Products",
    "stage": "Stages",
    "contact_region": "Contact Regions",
}
CATEGORIES = list(CATEGORY_LABELS.keys())


def _admin_required():
    if not current_user.is_admin:
        abort(403)


@settings_bp.route("/settings/picklists")
@login_required
def picklists():
    _admin_required()
    rows = PicklistItem.query.order_by(PicklistItem.category, PicklistItem.sort_order, PicklistItem.value).all()
    by_cat = {cat: [] for cat in CATEGORIES}
    for r in rows:
        if r.category in by_cat:
            by_cat[r.category].append(r)
    return render_template(
        "settings/picklists.html",
        active_page="settings",
        by_cat=by_cat,
        category_labels=CATEGORY_LABELS,
        categories=CATEGORIES,
    )


@settings_bp.route("/settings/picklists/add", methods=["POST"])
@login_required
def add_picklist_item():
    _admin_required()
    category = request.form.get("category", "").strip()
    value = request.form.get("value", "").strip()
    is_fire = request.form.get("is_fire") == "1"

    if category not in CATEGORIES or not value:
        flash("Invalid category or empty value.", "error")
        return redirect(url_for("settings.picklists"))

    existing = PicklistItem.query.filter_by(category=category, value=value).first()
    if existing:
        flash(f'"{value}" already exists in {CATEGORY_LABELS[category]}.', "error")
        return redirect(url_for("settings.picklists"))

    max_order = db.session.query(db.func.max(PicklistItem.sort_order)).filter_by(category=category).scalar() or 0
    item = PicklistItem(category=category, value=value, sort_order=max_order + 1, is_fire=is_fire)
    db.session.add(item)
    db.session.commit()
    flash(f'Added "{value}" to {CATEGORY_LABELS[category]}.', "success")
    return redirect(url_for("settings.picklists"))


@settings_bp.route("/settings/picklists/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_picklist_item(item_id):
    _admin_required()
    item = PicklistItem.query.get_or_404(item_id)
    label = CATEGORY_LABELS.get(item.category, item.category)
    db.session.delete(item)
    db.session.commit()
    flash(f'Removed "{item.value}" from {label}.', "success")
    return redirect(url_for("settings.picklists"))
