"""Dashboard Blueprint — Landing page"""
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, session
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import ActivityLog, Job, JobAction, Lead

dashboard_bp = Blueprint("dashboard", __name__)


def _quarter_bounds(today):
    """Return (start, end) dates for the current calendar quarter."""
    q_start_month = ((today.month - 1) // 3) * 3 + 1
    q_start = date(today.year, q_start_month, 1)
    next_month = q_start_month + 3
    if next_month > 12:
        q_end = date(today.year + 1, next_month - 12, 1) - timedelta(days=1)
    else:
        q_end = date(today.year, next_month, 1) - timedelta(days=1)
    return q_start, q_end


@dashboard_bp.route("/")
@login_required
def index():
    region = session.get("region", "all")
    today = date.today()

    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    active_statuses = ["Hot", "Long Burn"]

    def by_region(q, model):
        if region != "all":
            q = q.filter(model.region == region)
        return q

    # ── Pipeline Value ────────────────────────────────────────────
    pipeline_value = by_region(
        db.session.query(func.sum(Lead.value)).filter(Lead.status.in_(active_statuses)),
        Lead,
    ).scalar() or 0

    # ── New This Month ────────────────────────────────────────────
    month_start = datetime(today.year, today.month, 1)
    new_this_month = by_region(
        Lead.query.filter(Lead.created_at >= month_start),
        Lead,
    ).count()

    # ── Overdue ───────────────────────────────────────────────────
    overdue_count = by_region(
        Lead.query.filter(Lead.follow_up < today, Lead.status.in_(active_statuses)),
        Lead,
    ).count()

    # ── Active Jobs ───────────────────────────────────────────────
    active_jobs = by_region(
        Job.query.filter(Job.status == "Active"),
        Job,
    ).count()

    # ── Awaiting Action ───────────────────────────────────────────
    # Jobs that have at least one unchecked, non-NA action
    unchecked_job_ids = (
        db.session.query(JobAction.job_id)
        .filter(JobAction.checked == False, JobAction.is_na == False)  # noqa: E712
        .distinct()
        .subquery()
    )
    awaiting_action = by_region(
        Job.query.filter(Job.id.in_(unchecked_job_ids)),
        Job,
    ).count()

    # ── Active Leads Count (Hot + Long Burn) ─────────────────────
    active_leads_count = by_region(
        Lead.query.filter(Lead.status.in_(active_statuses)),
        Lead,
    ).count()

    # ── Won This Quarter ──────────────────────────────────────────
    q_start, q_end = _quarter_bounds(today)
    won_q = by_region(
        Lead.query.filter(
            Lead.status == "Won",
            Lead.won_date >= q_start,
            Lead.won_date <= q_end,
        ),
        Lead,
    )
    won_this_qtr_count = won_q.count()
    won_this_quarter = by_region(
        db.session.query(func.sum(Lead.value)).filter(
            Lead.status == "Won",
            Lead.won_date >= q_start,
            Lead.won_date <= q_end,
        ),
        Lead,
    ).scalar() or 0

    # ── Recent Activity ───────────────────────────────────────────
    ra_q = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    if region != "all":
        ra_q = ra_q.filter(ActivityLog.region == region)
    recent_activity = ra_q.limit(10).all()

    # ── Upcoming Follow-ups ───────────────────────────────────────
    uf_q = by_region(
        Lead.query.filter(
            Lead.follow_up.isnot(None),
            Lead.status.in_(active_statuses),
        ).order_by(Lead.follow_up.asc()),
        Lead,
    )
    upcoming_followups = [
        {"lead": lead, "days_until": (lead.follow_up - today).days}
        for lead in uf_q.limit(8).all()
    ]

    # ── Greeting name ─────────────────────────────────────────────
    greeting_name = current_user.display_name.split()[0]

    return render_template(
        "dashboard/index.html",
        active_page="dashboard",
        region=region,
        greeting=greeting,
        greeting_name=greeting_name,
        pipeline_value=pipeline_value,
        active_leads_count=active_leads_count,
        new_this_month=new_this_month,
        overdue_count=overdue_count,
        active_jobs=active_jobs,
        awaiting_action=awaiting_action,
        won_this_quarter=won_this_quarter,
        won_this_qtr_count=won_this_qtr_count,
        recent_activity=recent_activity,
        upcoming_followups=upcoming_followups,
        today=today,
    )
