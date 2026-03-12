"""Jobs Blueprint — Job management"""
from collections import defaultdict
from datetime import date, datetime

from flask import (
    Blueprint, render_template, render_template_string, session,
    request, redirect, url_for, flash, jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    ActivityLog, Contact, ContactLink, Door,
    Job, JobAction, JobNote, Lead, LeadNote, User, utcnow,
)

jobs_bp = Blueprint("jobs", __name__)
PER_PAGE = 25


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _apply_form_to_job(job, form):
    """Write form fields onto a Job instance."""
    job.job_number = form.get("job_number", "").strip()
    job.job_name = form.get("job_name", "").strip()
    job.status = form.get("status", "Active")
    job.job_type = form.get("job_type", "").strip() or None
    job.industry = form.get("industry", "").strip() or None
    job.address = form.get("address", "").strip() or None
    job.territory = form.get("territory", "").strip() or None
    job.region = form.get("region", "au")

    try:
        job.au_sell_price = float(form.get("au_sell_price") or 0) or None
    except (ValueError, TypeError):
        job.au_sell_price = None

    try:
        job.nz_sell_price = float(form.get("nz_sell_price") or 0) or None
    except (ValueError, TypeError):
        job.nz_sell_price = None

    try:
        job.progress_pct = int(form.get("progress_pct") or 0)
    except (ValueError, TypeError):
        job.progress_pct = 0

    for field in (
        "manufacture_start", "manufacture_end",
        "shipping_start", "shipping_end",
        "installation_start", "installation_end",
    ):
        val = (form.get(field) or "").strip()
        if val:
            try:
                setattr(job, field, date.fromisoformat(val))
            except ValueError:
                pass
        else:
            setattr(job, field, None)


def _apply_form_to_door(door, form):
    door.door_number = form.get("door_number", "").strip() or None
    door.location = form.get("location", "").strip() or None
    door.type = form.get("type", "").strip() or None
    door.configuration = form.get("configuration", "").strip() or None
    door.door_colour = form.get("door_colour", "").strip() or None
    door.track_colour = form.get("track_colour", "").strip() or None
    door.latch_lock = form.get("latch_lock", "").strip() or None
    door.stack = form.get("stack", "").strip() or None
    door.sweep = form.get("sweep", "").strip() or None
    try:
        door.width = float(form.get("width") or 0) or None
    except (ValueError, TypeError):
        door.width = None
    try:
        door.height = float(form.get("height") or 0) or None
    except (ValueError, TypeError):
        door.height = None


def _log(user_id, region, entity_id, action, message):
    db.session.add(ActivityLog(
        user_id=user_id, region=region,
        entity_type="job", entity_id=entity_id,
        action=action, message=message,
    ))


def _actions_by_category(job):
    """Group job actions by category, ordered by position."""
    result = defaultdict(list)
    for action in sorted(job.actions, key=lambda a: (a.category or "", a.position or 0)):
        result[action.category or "General"].append(action)
    return dict(result)


def _region_filter(q, model, region):
    if region != "all":
        q = q.filter(model.region == region)
    return q


# ─────────────────────────────────────────────────────────────────
# NOTE PARTIAL — rendered for AJAX note response
# ─────────────────────────────────────────────────────────────────

NOTE_PARTIAL = """
<div class="note-item" id="note-{{ note.id }}">
  <div class="note-avatar">{{ initials }}</div>
  <div class="note-body">
    <div class="note-meta">
      <strong>{{ name }}</strong> &nbsp;·&nbsp; just now
    </div>
    <div class="note-text">{{ note.note_text }}</div>
  </div>
</div>
"""


# ─────────────────────────────────────────────────────────────────
# CONTACT ROW PARTIAL — rendered for AJAX link response
# ─────────────────────────────────────────────────────────────────

CONTACT_ROW_PARTIAL = """
<div class="contact-row" id="clink-{{ link.id }}">
  <div class="contact-info">
    <strong>{{ c.name }}</strong>
    <div class="contact-sub">
      {% if c.linked_company %}{{ c.linked_company.name }}{% elif c.company %}{{ c.company }}{% endif %}
      {% if c.phone %}&nbsp;·&nbsp; {{ c.phone }}{% endif %}
      {% if c.email %}&nbsp;·&nbsp; {{ c.email }}{% endif %}
    </div>
  </div>
  <button class="btn btn-ghost btn-xs" onclick="unlinkContact({{ link.id }}, {{ job_id }}, {{ c.id }})">Unlink</button>
</div>
"""


# ─────────────────────────────────────────────────────────────────
# LIST VIEW
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/")
@login_required
def index():
    region = session.get("region", "all")
    today = date.today()

    statuses = request.args.getlist("status") or ["Active", "On Hold"]
    q_search = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    # ── KPIs ──────────────────────────────────────────────────────
    def _count_status(s):
        q = Job.query.filter(Job.status == s)
        return _region_filter(q, Job, region).count()

    active_count = _count_status("Active")
    hold_count = _count_status("On Hold")

    year_start = datetime(today.year, 1, 1)
    complete_year = _region_filter(
        Job.query.filter(Job.status == "Complete", Job.created_at >= year_start),
        Job, region,
    ).count()

    # Total active value = sum of au+nz sell price for Active jobs
    active_jobs_q = _region_filter(
        Job.query.filter(Job.status == "Active"), Job, region
    ).all()
    total_active_value = sum(
        (j.au_sell_price or 0) + (j.nz_sell_price or 0)
        for j in active_jobs_q
    )

    kpis = {
        "active_count": active_count,
        "hold_count": hold_count,
        "complete_year": complete_year,
        "total_active_value": total_active_value,
    }

    # ── Job query ─────────────────────────────────────────────────
    query = Job.query
    query = _region_filter(query, Job, region)

    if statuses:
        query = query.filter(Job.status.in_(statuses))

    if q_search:
        like = f"%{q_search}%"
        query = query.filter(or_(
            Job.job_number.ilike(like),
            Job.job_name.ilike(like),
            Job.address.ilike(like),
            Job.territory.ilike(like),
        ))

    query = query.order_by(Job.created_at.desc())
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    jobs = pagination.items

    # Load linked leads for display (avoid N+1 by using subquery pattern on small data)
    # Jobs have a backref .lead via Lead.job_id
    filters = {"statuses": statuses, "q": q_search}

    return render_template(
        "jobs/index.html",
        active_page="jobs",
        region=region,
        jobs=jobs,
        pagination=pagination,
        kpis=kpis,
        filters=filters,
        today=today,
    )


# ─────────────────────────────────────────────────────────────────
# NEW JOB
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/new", methods=["POST"])
@login_required
def new_job():
    region = session.get("region", "all")
    if region == "all":
        region = current_user.default_region

    job_number = request.form.get("job_number", "").strip()
    if not job_number:
        flash("Job number is required.", "error")
        return redirect(url_for("jobs.index"))

    existing = Job.query.filter_by(job_number=job_number).first()
    if existing:
        flash(f'Job number "{job_number}" already exists.', "error")
        return redirect(url_for("jobs.index"))

    job_name = request.form.get("job_name", "").strip()
    if not job_name:
        flash("Job name is required.", "error")
        return redirect(url_for("jobs.index"))

    job = Job(created_by=current_user.id, updated_by=current_user.id)
    _apply_form_to_job(job, request.form)
    db.session.add(job)
    db.session.flush()  # get job.id

    # ── Lead → Job conversion ─────────────────────────────────────
    lead_id = request.form.get("lead_id", type=int)
    if lead_id:
        lead = Lead.query.get(lead_id)
        if lead:
            # Override blanks from lead data (form fields take precedence)
            if not job.job_name:
                job.job_name = lead.project_name
            if not job.territory:
                job.territory = lead.state
            if not job.industry:
                job.industry = lead.application
            if not job.region or job.region == "au":
                job.region = lead.region
            if lead.region == "nz" and not job.nz_sell_price:
                job.nz_sell_price = lead.value
            elif not job.au_sell_price:
                job.au_sell_price = lead.value

            # Copy contact links from lead
            for ll in ContactLink.query.filter_by(lead_id=lead.id).all():
                # avoid duplicates if already linked via another path
                already = ContactLink.query.filter_by(contact_id=ll.contact_id, job_id=job.id).first()
                if not already:
                    db.session.add(ContactLink(
                        contact_id=ll.contact_id,
                        job_id=job.id,
                        is_primary=ll.is_primary,
                    ))

            # Copy lead notes → job notes (skip contact-log entries)
            for ln in lead.notes.filter_by(is_contact_log=False).order_by(LeadNote.created_at).all():
                db.session.add(JobNote(
                    job_id=job.id,
                    user_id=ln.user_id,
                    note_text=ln.note_text,
                    created_at=ln.created_at,
                ))

            # Link lead to this job
            lead.job_id = job.id

    _log(current_user.id, job.region, job.id, "created", f"Created job: {job.job_name}")
    db.session.commit()

    flash(f'Job "{job.job_name}" created.', "success")
    return redirect(url_for("jobs.detail", id=job.id))


# ─────────────────────────────────────────────────────────────────
# DETAIL VIEW
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/<int:id>")
@login_required
def detail(id):
    job = Job.query.options(
        joinedload(Job.doors),
        joinedload(Job.actions).joinedload(JobAction.checker),
    ).get_or_404(id)

    notes = job.job_notes.order_by(JobNote.created_at.desc()).all()
    contacts = (
        ContactLink.query
        .filter_by(job_id=job.id)
        .options(joinedload(ContactLink.contact).joinedload(Contact.linked_company))
        .all()
    )
    actions_by_cat = _actions_by_category(job)
    activity = (
        ActivityLog.query
        .filter_by(entity_type="job", entity_id=job.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "jobs/detail.html",
        active_page="jobs",
        job=job,
        doors=job.doors,
        notes=notes,
        contacts=contacts,
        actions_by_category=actions_by_cat,
        activity=activity,
    )


# ─────────────────────────────────────────────────────────────────
# EDIT JOB
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/<int:id>/edit", methods=["POST"])
@login_required
def edit_job(id):
    job = Job.query.get_or_404(id)
    old_status = job.status
    _apply_form_to_job(job, request.form)
    job.updated_by = current_user.id

    changes = []
    if old_status != job.status:
        changes.append(f"status → {job.status}")
    msg = f"Updated job: {job.job_name}" + (f" ({', '.join(changes)})" if changes else "")
    _log(current_user.id, job.region, job.id, "updated", msg)
    db.session.commit()

    flash(f'Job "{job.job_name}" updated.', "success")
    return redirect(url_for("jobs.detail", id=id))


# ─────────────────────────────────────────────────────────────────
# STATUS UPDATE
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/<int:id>/status", methods=["POST"])
@login_required
def update_status(id):
    job = Job.query.get_or_404(id)
    new_status = request.form.get("status", "").strip()
    if new_status in ("Active", "On Hold", "Complete"):
        old = job.status
        job.status = new_status
        job.updated_by = current_user.id
        _log(current_user.id, job.region, job.id, "status_changed",
             f"Status changed: {old} → {new_status}")
        db.session.commit()
        flash(f'Status updated to "{new_status}".', "success")
    return redirect(url_for("jobs.detail", id=id))


# ─────────────────────────────────────────────────────────────────
# DOORS
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/<int:id>/door/new", methods=["POST"])
@login_required
def new_door(id):
    job = Job.query.get_or_404(id)
    door = Door(job_id=job.id)
    _apply_form_to_door(door, request.form)
    db.session.add(door)
    _log(current_user.id, job.region, job.id, "updated",
         f"Added door: {door.door_number or 'new'}")
    db.session.commit()
    return redirect(url_for("jobs.detail", id=id) + "#doors")


@jobs_bp.route("/<int:id>/door/<int:did>/edit", methods=["POST"])
@login_required
def edit_door(id, did):
    job = Job.query.get_or_404(id)
    door = Door.query.get_or_404(did)
    if door.job_id != id:
        flash("Door not found.", "error")
        return redirect(url_for("jobs.detail", id=id))
    _apply_form_to_door(door, request.form)
    _log(current_user.id, job.region, job.id, "updated",
         f"Edited door: {door.door_number or did}")
    db.session.commit()
    return redirect(url_for("jobs.detail", id=id) + "#doors")


@jobs_bp.route("/<int:id>/door/<int:did>/delete", methods=["POST"])
@login_required
def delete_door(id, did):
    job = Job.query.get_or_404(id)
    door = Door.query.get_or_404(did)
    if door.job_id != id:
        flash("Door not found.", "error")
        return redirect(url_for("jobs.detail", id=id))
    db.session.delete(door)
    _log(current_user.id, job.region, job.id, "updated",
         f"Deleted door: {door.door_number or did}")
    db.session.commit()
    return redirect(url_for("jobs.detail", id=id) + "#doors")


# ─────────────────────────────────────────────────────────────────
# ACTION TOGGLE (AJAX)
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/<int:id>/action/<int:aid>/toggle", methods=["POST"])
@login_required
def toggle_action(id, aid):
    job = Job.query.get_or_404(id)
    action = JobAction.query.get_or_404(aid)
    if action.job_id != id:
        return jsonify({"ok": False, "error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if data.get("na"):
        action.is_na = not action.is_na
        if action.is_na:
            action.checked = False
            action.checked_at = None
            action.checked_by = None
    else:
        action.checked = not action.checked
        if action.checked:
            action.checked_at = utcnow()
            action.checked_by = current_user.id
            action.is_na = False
        else:
            action.checked_at = None
            action.checked_by = None

    db.session.commit()

    # Recalculate pct
    all_actions = JobAction.query.filter_by(job_id=id).all()
    countable = [a for a in all_actions if not a.is_na]
    checked = [a for a in countable if a.checked]
    pct = round(len(checked) / len(countable) * 100) if countable else 0

    # Update job progress_pct
    job.progress_pct = pct
    db.session.commit()

    checker_info = ""
    if action.checked and action.checker:
        checker_info = action.checker.display_name

    return jsonify({
        "ok": True,
        "checked": action.checked,
        "is_na": action.is_na,
        "pct": pct,
        "checker_info": checker_info,
    })


# ─────────────────────────────────────────────────────────────────
# NOTES (AJAX)
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/<int:id>/note/new", methods=["POST"])
@login_required
def new_note(id):
    job = Job.query.get_or_404(id)
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or request.form.get("text", "")).strip()
    if not text:
        return jsonify({"ok": False, "error": "Note text required"}), 400

    note = JobNote(job_id=job.id, user_id=current_user.id, note_text=text)
    db.session.add(note)
    _log(current_user.id, job.region, job.id, "note",
         f"Added note: {text[:80]}")
    db.session.commit()

    # Build initials and name for partial
    user = current_user
    name = user.display_name or user.username
    parts = name.split()
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    html = render_template_string(NOTE_PARTIAL, note=note, initials=initials, name=name)
    return jsonify({"ok": True, "html": html})


# ─────────────────────────────────────────────────────────────────
# CONTACTS (AJAX)
# ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/search/contacts")
@login_required
def search_contacts():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    like = f"%{q}%"
    contacts = Contact.query.filter(Contact.name.ilike(like)).limit(10).all()
    results = [
        {
            "id": c.id,
            "name": c.name,
            "company": (c.linked_company.name if c.linked_company else c.company) or "",
            "phone": c.phone or "",
            "email": c.email or "",
        }
        for c in contacts
    ]
    return jsonify({"results": results})


@jobs_bp.route("/<int:id>/contact/link", methods=["POST"])
@login_required
def link_contact(id):
    job = Job.query.get_or_404(id)
    data = request.get_json(silent=True) or {}
    contact_id = data.get("contact_id")
    if not contact_id:
        return jsonify({"ok": False, "error": "contact_id required"}), 400

    contact = Contact.query.get_or_404(contact_id)

    # Check not already linked
    existing = ContactLink.query.filter_by(job_id=id, contact_id=contact_id).first()
    if existing:
        return jsonify({"ok": False, "error": "Already linked"}), 409

    link = ContactLink(contact_id=contact_id, job_id=id, is_primary=False)
    db.session.add(link)
    db.session.commit()

    # Reload with relationships
    link = ContactLink.query.options(
        joinedload(ContactLink.contact).joinedload(Contact.linked_company)
    ).get(link.id)
    c = link.contact

    html = render_template_string(CONTACT_ROW_PARTIAL, link=link, c=c, job_id=id)
    return jsonify({"ok": True, "html": html})


@jobs_bp.route("/<int:id>/contact/<int:cid>/unlink", methods=["POST"])
@login_required
def unlink_contact(id, cid):
    Job.query.get_or_404(id)  # ensure job exists
    link = ContactLink.query.filter_by(job_id=id, contact_id=cid).first_or_404()
    db.session.delete(link)
    db.session.commit()
    return jsonify({"ok": True})
