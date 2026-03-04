"""Pipeline Blueprint — Lead tracking"""
from datetime import date

from flask import (
    Blueprint, render_template, session, request,
    redirect, url_for, flash, jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import func, asc, desc, nullslast, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import ActivityLog, Lead, LeadNote, User

pipeline_bp = Blueprint("pipeline", __name__)

PER_PAGE = 25
PRODUCT_LIST = ["DuraSound", "Operable Wall", "FireGuard", "DuraFlex"]
LOST_REASONS = [
    "Price", "Competitor", "Project Cancelled",
    "No Decision", "Timing", "Other",
]


def _region_filter(q, model, region):
    if region != "all":
        q = q.filter(model.region == region)
    return q


def _kpi(statuses, region):
    """Return (count, sum_value) for the given statuses, filtered by region."""
    q = db.session.query(
        func.count(Lead.id),
        func.sum(Lead.value),
    ).filter(Lead.status.in_(statuses))
    q = _region_filter(q, Lead, region)
    count, total = q.one()
    return (count or 0), (total or 0)


# ─────────────────────────────────────────────────────────────────
# LIST VIEW
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/")
@login_required
def index():
    region = session.get("region", "all")
    today = date.today()

    # ── Query params ─────────────────────────────────────────────
    statuses = request.args.getlist("status") or ["Hot", "Long Burn"]
    brands = request.args.getlist("brand")
    state = request.args.get("state", "")
    application = request.args.get("application", "")
    sort = request.args.get("sort", "follow_up")
    page = request.args.get("page", 1, type=int)
    q_search = request.args.get("q", "").strip()

    # ── Base query ────────────────────────────────────────────────
    query = Lead.query.options(joinedload(Lead.assigned_user))
    query = _region_filter(query, Lead, region)

    if statuses:
        query = query.filter(Lead.status.in_(statuses))
    if brands:
        query = query.filter(Lead.brand.in_(brands))
    if state:
        query = query.filter(Lead.state == state)
    if application:
        query = query.filter(Lead.application == application)
    if q_search:
        like = f"%{q_search}%"
        query = query.filter(or_(
            Lead.project_name.ilike(like),
            Lead.client.ilike(like),
            Lead.contact_name.ilike(like),
            Lead.next_action.ilike(like),
        ))

    # ── Sort ──────────────────────────────────────────────────────
    if sort == "value_desc":
        query = query.order_by(desc(Lead.value))
    elif sort == "value_asc":
        query = query.order_by(asc(Lead.value))
    elif sort == "recent":
        query = query.order_by(desc(Lead.created_at))
    else:  # follow_up — nulls last
        query = query.order_by(nullslast(asc(Lead.follow_up)))

    # ── Paginate ──────────────────────────────────────────────────
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    leads = pagination.items

    # ── KPIs (region-filtered, no other filters) ──────────────────
    active_count, active_value = _kpi(["Hot", "Long Burn"], region)
    hot_count, hot_value = _kpi(["Hot"], region)
    burn_count, burn_value = _kpi(["Long Burn"], region)
    won_count, won_value = _kpi(["Won"], region)
    lost_count, lost_value = _kpi(["Lost"], region)
    kpis = {
        "active_value": active_value, "active_count": active_count,
        "hot_count": hot_count, "hot_value": hot_value,
        "burn_count": burn_count, "burn_value": burn_value,
        "won_count": won_count, "won_value": won_value,
        "lost_count": lost_count, "lost_value": lost_value,
    }

    # ── Filter dropdown options ───────────────────────────────────
    def distinct_vals(col):
        q = db.session.query(col.distinct()).filter(col.isnot(None), col != "")
        if region != "all":
            q = q.filter(Lead.region == region)
        return sorted(r[0] for r in q.all())

    states_list = distinct_vals(Lead.state)
    applications_list = distinct_vals(Lead.application)

    # ── Nav badge: overdue hot/burn leads ─────────────────────────
    pipeline_overdue = _region_filter(
        Lead.query.filter(
            Lead.follow_up < today,
            Lead.status.in_(["Hot", "Long Burn"]),
        ),
        Lead, region,
    ).count()

    # ── Users for assigned-to dropdown ───────────────────────────
    users = User.query.order_by(User.display_name).all()

    filters = {
        "statuses": statuses, "brands": brands,
        "state": state, "application": application,
        "sort": sort, "q": q_search,
    }

    return render_template(
        "pipeline/index.html",
        active_page="pipeline",
        region=region,
        leads=leads,
        pagination=pagination,
        filters=filters,
        kpis=kpis,
        states_list=states_list,
        applications_list=applications_list,
        users=users,
        today=today,
        product_list=PRODUCT_LIST,
        lost_reasons=LOST_REASONS,
        pipeline_overdue=pipeline_overdue,
    )


# ─────────────────────────────────────────────────────────────────
# LEAD JSON (modal pre-fill)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/<int:id>")
@login_required
def get_lead(id):
    lead = Lead.query.get_or_404(id)
    return jsonify({
        "id": lead.id,
        "project_name": lead.project_name,
        "client": lead.client,
        "contact_name": lead.contact_name or "",
        "phone": lead.phone or "",
        "email": lead.email or "",
        "brand": lead.brand or "MPA",
        "status": lead.status,
        "state": lead.state or "",
        "application": lead.application or "",
        "lead_source": lead.lead_source or "",
        "value": lead.value or 0,
        "follow_up": lead.follow_up.isoformat() if lead.follow_up else "",
        "quote_date": lead.quote_date.isoformat() if lead.quote_date else "",
        "last_contact": lead.last_contact.isoformat() if lead.last_contact else "",
        "won_date": lead.won_date.isoformat() if lead.won_date else "",
        "products": lead.get_products_list(),
        "next_action": lead.next_action or "",
        "lost_reason": lead.lost_reason or "",
        "lost_notes": lead.lost_notes or "",
        "assigned_to": lead.assigned_to or "",
        "region": lead.region,
    })


# ─────────────────────────────────────────────────────────────────
# HELPERS shared by new / edit
# ─────────────────────────────────────────────────────────────────

def _apply_form_to_lead(lead, form):
    """Write form data onto a Lead instance."""
    lead.project_name = form.get("project_name", "").strip()
    lead.client = form.get("client", "").strip()
    lead.contact_name = form.get("contact_name", "").strip()
    lead.phone = form.get("phone", "").strip()
    lead.email = form.get("email", "").strip()
    lead.brand = form.get("brand", "MPA")
    lead.status = form.get("status", "Hot")
    lead.state = form.get("state", "").strip()
    lead.application = form.get("application", "").strip()
    lead.lead_source = form.get("lead_source", "").strip()
    lead.next_action = form.get("next_action", "").strip()
    lead.lost_reason = form.get("lost_reason", "").strip()
    lead.lost_notes = form.get("lost_notes", "").strip()

    try:
        lead.value = float(form.get("value") or 0)
    except (ValueError, TypeError):
        lead.value = 0

    for field in ("follow_up", "quote_date", "last_contact", "won_date"):
        val = (form.get(field) or "").strip()
        if val:
            try:
                setattr(lead, field, date.fromisoformat(val))
            except ValueError:
                pass
        else:
            setattr(lead, field, None)

    assigned = form.get("assigned_to", "")
    try:
        lead.assigned_to = int(assigned) if assigned else None
    except (ValueError, TypeError):
        lead.assigned_to = None

    lead.set_products_list(form.getlist("products"))


def _safe_next(fallback):
    nxt = request.form.get("next", "")
    if nxt.startswith("/pipeline"):
        return nxt
    return fallback


# ─────────────────────────────────────────────────────────────────
# NEW LEAD
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/new", methods=["POST"])
@login_required
def new_lead():
    region = session.get("region", "all")
    if region == "all":
        region = current_user.default_region

    lead = Lead(region=region, created_by=current_user.id, updated_by=current_user.id)
    _apply_form_to_lead(lead, request.form)
    db.session.add(lead)
    db.session.flush()

    db.session.add(ActivityLog(
        user_id=current_user.id, region=region,
        entity_type="lead", entity_id=lead.id,
        action="created", message=f"Created lead: {lead.project_name}",
    ))
    db.session.commit()

    flash(f'Lead "{lead.project_name}" created successfully.', "success")
    return redirect(_safe_next(url_for("pipeline.index")))


# ─────────────────────────────────────────────────────────────────
# EDIT LEAD
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/<int:id>/edit", methods=["POST"])
@login_required
def edit_lead(id):
    lead = Lead.query.get_or_404(id)
    _apply_form_to_lead(lead, request.form)
    lead.updated_by = current_user.id

    db.session.add(ActivityLog(
        user_id=current_user.id, region=lead.region,
        entity_type="lead", entity_id=lead.id,
        action="updated", message=f"Updated lead: {lead.project_name}",
    ))
    db.session.commit()

    flash(f'Lead "{lead.project_name}" updated.', "success")
    return redirect(_safe_next(url_for("pipeline.index")))


# ─────────────────────────────────────────────────────────────────
# DELETE LEAD (admin only)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/<int:id>/delete", methods=["POST"])
@login_required
def delete_lead(id):
    if not current_user.is_admin:
        flash("Only admins can delete leads.", "error")
        return redirect(url_for("pipeline.index"))

    lead = Lead.query.get_or_404(id)
    name = lead.project_name
    db.session.delete(lead)
    db.session.commit()

    flash(f'Lead "{name}" deleted.', "success")
    return redirect(url_for("pipeline.index"))


# ─────────────────────────────────────────────────────────────────
# ADD NOTE (AJAX)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/<int:id>/note", methods=["POST"])
@login_required
def add_note(id):
    lead = Lead.query.get_or_404(id)
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or request.form.get("text", "")).strip()
    if not text:
        return jsonify({"ok": False, "error": "Note text required"}), 400
    db.session.add(LeadNote(lead_id=lead.id, user_id=current_user.id, note_text=text))
    db.session.commit()
    return jsonify({"ok": True})
