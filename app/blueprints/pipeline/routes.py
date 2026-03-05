"""Pipeline Blueprint — Lead tracking"""
from datetime import date, datetime, timedelta

from flask import (
    Blueprint, render_template, session, request,
    redirect, url_for, flash, jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import func, asc, desc, nullslast, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import ActivityLog, Company, Contact, Lead, LeadNote, PicklistItem, User

pipeline_bp = Blueprint("pipeline", __name__)

PER_PAGE = 25
AU_STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT", "INTL"]


def _load_picklists():
    """Load all picklist categories in one query. Returns a dict keyed by category."""
    rows = PicklistItem.query.order_by(PicklistItem.sort_order, PicklistItem.value).all()
    result = {}
    for r in rows:
        result.setdefault(r.category, []).append(r)
    return result


def _pl_values(pl, category):
    return [r.value for r in pl.get(category, [])]


def _fire_set(pl):
    return {r.value for r in pl.get("product", []) if r.is_fire}


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
    pl = _load_picklists()
    fire_products = _fire_set(pl)

    # ── Query params ─────────────────────────────────────────────
    statuses = request.args.getlist("status") or ["Hot", "Long Burn", "Dead"]
    brands = request.args.getlist("brand")
    states = request.args.getlist("state")
    applications = request.args.getlist("application")
    lead_sources = request.args.getlist("lead_source")
    products = request.args.getlist("product")
    sort = request.args.get("sort", "follow_up")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", PER_PAGE, type=int)
    if per_page not in (25, 50, 100):
        per_page = PER_PAGE
    q_search = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    val_min = request.args.get("val_min", type=float)
    val_max = request.args.get("val_max", type=float)

    # ── Base query ────────────────────────────────────────────────
    query = Lead.query.options(joinedload(Lead.assigned_user))
    query = _region_filter(query, Lead, region)

    if statuses:
        query = query.filter(Lead.status.in_(statuses))
    if brands:
        query = query.filter(Lead.brand.in_(brands))
    if states:
        query = query.filter(Lead.state.in_(states))
    if applications:
        query = query.filter(Lead.application.in_(applications))
    if lead_sources:
        query = query.filter(Lead.lead_source.in_(lead_sources))
    if products:
        query = query.filter(or_(*[Lead.products.contains(p) for p in products]))
    if date_from:
        try:
            query = query.filter(Lead.quote_date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Lead.quote_date <= date.fromisoformat(date_to))
        except ValueError:
            pass
    if val_min is not None:
        query = query.filter(Lead.value >= val_min)
    if val_max is not None:
        query = query.filter(Lead.value <= val_max)
    if q_search:
        like = f"%{q_search}%"
        query = query.filter(or_(
            Lead.project_name.ilike(like),
            Lead.client.ilike(like),
            Lead.contact_name.ilike(like),
            Lead.next_action.ilike(like),
        ))

    # ── Sort ──────────────────────────────────────────────────────
    sort_col_map = {
        "value_desc": desc(Lead.value),
        "value_asc":  asc(Lead.value),
        "recent":     desc(Lead.created_at),
        "client":     asc(Lead.client),
        "project":    asc(Lead.project_name),
        "state":      asc(Lead.state),
        "last_touch": desc(Lead.last_contact),
        "quote_date": desc(Lead.quote_date),
    }
    order = sort_col_map.get(sort, nullslast(asc(Lead.follow_up)))
    query = query.order_by(order)

    # ── Paginate ──────────────────────────────────────────────────
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    leads = pagination.items

    # ── KPIs (region-filtered, no other filters) ──────────────────
    active_count, active_value = _kpi(["Hot", "Long Burn"], region)
    hot_count, hot_value = _kpi(["Hot"], region)
    burn_count, burn_value = _kpi(["Long Burn"], region)
    won_count, won_value = _kpi(["Won"], region)
    lost_count, lost_value = _kpi(["Lost"], region)

    closed = won_count + lost_count
    win_rate = round(won_count / closed * 100) if closed else 0

    # Avg value: fire vs non-fire products
    all_active = _region_filter(
        Lead.query.filter(Lead.status.in_(["Hot", "Long Burn"])), Lead, region
    ).all()
    fire_leads = [l for l in all_active if any(p in fire_products for p in l.get_products_list())]
    nf_leads = [l for l in all_active if not any(p in fire_products for p in l.get_products_list())]
    avg_fire = round(sum(l.value or 0 for l in fire_leads) / len(fire_leads)) if fire_leads else 0
    avg_nf = round(sum(l.value or 0 for l in nf_leads) / len(nf_leads)) if nf_leads else 0

    # This month count
    month_start = datetime(today.year, today.month, 1)
    month_end = datetime(today.year + 1, 1, 1) if today.month == 12 else datetime(today.year, today.month + 1, 1)
    this_month_count = _region_filter(
        Lead.query.filter(
            Lead.created_at >= month_start,
            Lead.created_at < month_end,
        ), Lead, region
    ).count()

    # Overdue count (for both nav badge and KPI)
    overdue_count = _region_filter(
        Lead.query.filter(
            Lead.follow_up < today,
            Lead.status.in_(["Hot", "Long Burn"]),
        ), Lead, region,
    ).count()

    kpis = {
        "active_value": active_value, "active_count": active_count,
        "hot_count": hot_count, "hot_value": hot_value,
        "burn_count": burn_count, "burn_value": burn_value,
        "won_count": won_count, "won_value": won_value,
        "lost_count": lost_count, "lost_value": lost_value,
        "win_rate": win_rate,
        "avg_fire": avg_fire, "avg_nf": avg_nf,
        "this_month": this_month_count,
        "overdue_count": overdue_count,
    }

    # ── Pipeline bar data ─────────────────────────────────────────
    def _val(status):
        _, v = _kpi([status], region)
        return v or 0

    pb_hot = _val("Hot")
    pb_burn = _val("Long Burn")
    pb_won = _val("Won")
    pb_lost = _val("Lost")
    pb_total = (pb_hot + pb_burn + pb_won + pb_lost) or 1
    pipeline_bar = {
        "hot_pct": round(pb_hot / pb_total * 100, 1),
        "burn_pct": round(pb_burn / pb_total * 100, 1),
        "won_pct": round(pb_won / pb_total * 100, 1),
        "lost_pct": round(pb_lost / pb_total * 100, 1),
        "hot_val": pb_hot, "burn_val": pb_burn,
        "won_val": pb_won, "lost_val": pb_lost,
    }

    # ── Filter dropdown options ───────────────────────────────────
    def distinct_vals(col):
        q = db.session.query(col.distinct()).filter(col.isnot(None), col != "")
        if region != "all":
            q = q.filter(Lead.region == region)
        return sorted(r[0] for r in q.all())

    states_list = distinct_vals(Lead.state)
    applications_list = distinct_vals(Lead.application)
    sources_list = distinct_vals(Lead.lead_source)
    users = User.query.order_by(User.display_name).all()

    # ── Nav badge: overdue hot/burn leads ─────────────────────────
    pipeline_overdue = overdue_count

    # ── Overdue leads for alert banner ───────────────────────────
    overdue_leads = _region_filter(
        Lead.query.filter(
            Lead.follow_up < today,
            Lead.status.in_(["Hot", "Long Burn"]),
        ),
        Lead, region,
    ).order_by(Lead.follow_up).limit(5).all()

    filters = {
        "statuses": statuses, "brands": brands,
        "states": states, "applications": applications,
        "lead_sources": lead_sources, "products": products,
        "sort": sort, "q": q_search,
        "date_from": date_from, "date_to": date_to,
        "val_min": val_min or "", "val_max": val_max or "",
        "per_page": per_page,
    }

    return render_template(
        "pipeline/index.html",
        active_page="pipeline",
        region=region,
        leads=leads,
        pagination=pagination,
        filters=filters,
        kpis=kpis,
        pipeline_bar=pipeline_bar,
        states_list=states_list,
        applications_list=applications_list,
        sources_list=sources_list,
        users=users,
        today=today,
        product_list=_pl_values(pl, "product"),
        fire_products=fire_products,
        lost_reasons=_pl_values(pl, "lost_reason"),
        lead_sources=_pl_values(pl, "lead_source"),
        stages=_pl_values(pl, "stage"),
        au_states=AU_STATES,
        applications=_pl_values(pl, "application"),
        pipeline_overdue=pipeline_overdue,
        overdue_leads=overdue_leads,
    )


# ─────────────────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/analytics")
@login_required
def analytics():
    region = session.get("region", "all")
    today = date.today()
    pl = _load_picklists()
    fire_products = _fire_set(pl)

    # Date range params
    a_range = request.args.get("range", "all")
    a_from = request.args.get("from", "")
    a_to = request.args.get("to", "")

    # Compute date bounds
    if a_range == "30d":
        range_from = today - timedelta(days=30)
        range_to = today
    elif a_range == "90d":
        range_from = today - timedelta(days=90)
        range_to = today
    elif a_range == "6m":
        range_from = today - timedelta(days=183)
        range_to = today
    elif a_range == "1y":
        range_from = today - timedelta(days=365)
        range_to = today
    elif a_range == "custom" and a_from and a_to:
        try:
            range_from = date.fromisoformat(a_from)
            range_to = date.fromisoformat(a_to)
        except ValueError:
            range_from = range_to = None
    else:
        range_from = range_to = None

    # All leads (region filtered)
    q = Lead.query
    q = _region_filter(q, Lead, region)
    if range_from:
        q = q.filter(Lead.created_at >= range_from)
    if range_to:
        q = q.filter(Lead.created_at <= range_to)
    all_leads = q.all()

    # Product filter: 'standard' = no fire products, 'fire' = only fire products
    product_filter = request.args.get("product_filter", "all")
    if product_filter == "fire":
        all_leads = [l for l in all_leads if any(p in fire_products for p in l.get_products_list())]
    elif product_filter == "standard":
        all_leads = [l for l in all_leads if not any(p in fire_products for p in l.get_products_list())]

    active = [l for l in all_leads if l.status not in ("Dead", "Lost")]
    won = [l for l in all_leads if l.status == "Won"]
    lost = [l for l in all_leads if l.status == "Lost"]
    closed_count = len(won) + len(lost)
    win_rate = round(len(won) / closed_count * 100) if closed_count else 0

    # Fire vs non-fire
    fire = [l for l in active if any(p in fire_products for p in l.get_products_list())]
    nf = [l for l in active if not any(p in fire_products for p in l.get_products_list())]
    avg_nf = round(sum(l.value or 0 for l in nf) / len(nf)) if nf else 0
    avg_fire = round(sum(l.value or 0 for l in fire) / len(fire)) if fire else 0

    # Status donut
    status_segs = [
        {"lbl": "Hot", "count": sum(1 for l in all_leads if l.status == "Hot"), "col": "var(--red)"},
        {"lbl": "Long Burn", "count": sum(1 for l in all_leads if l.status == "Long Burn"), "col": "var(--amber)"},
        {"lbl": "Won", "count": len(won), "col": "var(--teal)"},
        {"lbl": "Lost", "count": len(lost), "col": "var(--violet)"},
        {"lbl": "Dead", "count": sum(1 for l in all_leads if l.status == "Dead"), "col": "var(--text-4)"},
    ]
    status_segs = [s for s in status_segs if s["count"] > 0]

    # Monthly (last 8 months)
    months = []
    for i in range(7, -1, -1):
        dt = today.replace(day=1) - timedelta(days=i * 28)
        # Normalize to first of month
        first = dt.replace(day=1)
        key = first.strftime("%Y-%m")
        lbl = first.strftime("%b")
        count = sum(1 for l in all_leads if l.created_at and l.created_at.strftime("%Y-%m") == key)
        months.append({"lbl": lbl, "count": count})

    # State breakdown
    state_data = []
    for s in AU_STATES:
        sl = [l for l in all_leads if l.state == s]
        if not sl:
            continue
        al = [l for l in sl if l.status not in ("Dead", "Lost")]
        state_data.append({
            "s": s,
            "count": len(sl),
            "val": sum(l.value or 0 for l in al),
            "active": len(al),
            "won": sum(1 for l in sl if l.status == "Won"),
        })
    state_data.sort(key=lambda d: d["val"], reverse=True)

    # Product breakdown
    prod_data = []
    for p in _pl_values(pl, "product"):
        p_leads = [l for l in all_leads if p in l.get_products_list()]
        if not p_leads:
            continue
        prod_data.append({
            "p": p,
            "count": len(p_leads),
            "val": sum(l.value or 0 for l in p_leads),
            "fire": p in fire_products,
        })
    prod_data.sort(key=lambda d: d["val"], reverse=True)

    # Lost reasons
    lost_reasons_tally = {}
    for l in lost:
        r = l.lost_reason or "Unknown"
        lost_reasons_tally[r] = lost_reasons_tally.get(r, 0) + 1
    lost_reason_rows = sorted(lost_reasons_tally.items(), key=lambda x: x[1], reverse=True)

    # Lead source performance
    source_data = []
    for src in _pl_values(pl, "lead_source"):
        in_src = [l for l in all_leads if l.lead_source == src]
        if not in_src:
            continue
        won_src = [l for l in in_src if l.status == "Won"]
        lost_src = [l for l in in_src if l.status == "Lost"]
        closed_src = len(won_src) + len(lost_src)
        conv_rate = round(len(won_src) / closed_src * 100) if closed_src else 0
        revenue = sum(l.value or 0 for l in won_src)
        avg_deal = round(revenue / len(won_src)) if won_src else 0
        pipe_val = sum(l.value or 0 for l in in_src if l.status in ("Hot", "Long Burn"))
        source_data.append({
            "src": src, "total": len(in_src),
            "won": len(won_src), "lost": len(lost_src),
            "closed": closed_src, "conv_rate": conv_rate,
            "revenue": revenue, "avg_deal": avg_deal, "pipe_val": pipe_val,
        })
    source_data.sort(key=lambda d: d["revenue"], reverse=True)

    # Time-to-win / time-to-loss
    def days_between(a, b):
        if not a or not b:
            return None
        try:
            da = a if isinstance(a, date) else date.fromisoformat(str(a))
            db_ = b if isinstance(b, date) else date.fromisoformat(str(b))
            return (db_ - da).days
        except Exception:
            return None

    ttw = [d for d in (days_between(l.quote_date, l.won_date) for l in won) if d is not None and d >= 0]
    avg_ttw = round(sum(ttw) / len(ttw)) if ttw else None
    median_ttw = sorted(ttw)[len(ttw) // 2] if ttw else None

    pipeline_leads = [l for l in all_leads if l.status in ("Hot", "Long Burn")]
    pipeline_val = sum(l.value or 0 for l in pipeline_leads)

    # Application performance
    app_names = _pl_values(pl, "application")
    app_data = []
    for app_name in app_names:
        al = [l for l in all_leads if l.application == app_name]
        if not al:
            continue
        won_al = [l for l in al if l.status == "Won"]
        lost_al = [l for l in al if l.status == "Lost"]
        closed_al = len(won_al) + len(lost_al)
        active_al = [l for l in al if l.status in ("Hot", "Long Burn")]
        conv_rate = round(len(won_al) / closed_al * 100) if closed_al else 0
        revenue = sum(l.value or 0 for l in won_al)
        avg_deal = round(revenue / len(won_al)) if won_al else 0
        active_val = sum(l.value or 0 for l in active_al)
        app_data.append({
            "app": app_name,
            "total": len(al),
            "won": len(won_al),
            "lost": len(lost_al),
            "active": len(active_al),
            "active_val": active_val,
            "revenue": revenue,
            "avg_deal": avg_deal,
            "conv_rate": conv_rate,
        })
    # also catch leads with apps not in the preset list
    for l in all_leads:
        if l.application and l.application not in app_names:
            app_name = l.application
            if not any(d["app"] == app_name for d in app_data):
                app_data.append({"app": app_name, "total": 1, "won": 0, "lost": 0,
                                  "active": 0, "active_val": 0, "revenue": 0, "avg_deal": 0, "conv_rate": 0})
    app_data.sort(key=lambda d: d["active_val"], reverse=True)
    top_app_value = max(app_data, key=lambda d: d["active_val"], default=None) if app_data else None
    top_app_wr = max(
        [d for d in app_data if (d["won"] + d["lost"]) >= 2],
        key=lambda d: d["conv_rate"], default=None
    )
    top_app_deal = max([d for d in app_data if d["won"] >= 1], key=lambda d: d["avg_deal"], default=None)

    # Revenue forecast (weighted by global win rate + sales cycle)
    global_wr = len(won) / closed_count if closed_count else 0.35
    avg_cycle = avg_ttw or 60
    forecast = {30: {"low": 0, "mid": 0, "high": 0},
                60: {"low": 0, "mid": 0, "high": 0},
                90: {"low": 0, "mid": 0, "high": 0}}
    for l in pipeline_leads:
        days_in = days_between(l.quote_date, today) or 0
        # Blended probability
        prob = min(global_wr * 1.1, 0.90)  # simple estimate; improve with more data
        val = l.value or 0
        remaining_cycle = max(avg_cycle - days_in, 0)
        for horizon in (30, 60, 90):
            prob_h = min(prob * (horizon / max(avg_cycle, 1)), prob)
            forecast[horizon]["mid"] += val * prob_h
            forecast[horizon]["low"] += val * prob_h * 0.6
            forecast[horizon]["high"] += val * min(prob_h * 1.4, 1.0)

    return render_template(
        "pipeline/analytics.html",
        active_page="pipeline",
        region=region,
        today=today,
        a_range=a_range,
        a_from=a_from,
        a_to=a_to,
        all_leads=all_leads,
        active=active,
        won=won,
        lost=lost,
        closed_count=closed_count,
        win_rate=win_rate,
        avg_nf=avg_nf,
        avg_fire=avg_fire,
        nf=nf,
        fire=fire,
        status_segs=status_segs,
        months=months,
        state_data=state_data,
        prod_data=prod_data,
        lost_reason_rows=lost_reason_rows,
        source_data=source_data,
        avg_ttw=avg_ttw,
        median_ttw=median_ttw,
        pipeline_leads=pipeline_leads,
        pipeline_val=pipeline_val,
        app_data=app_data,
        top_app_value=top_app_value,
        top_app_wr=top_app_wr,
        top_app_deal=top_app_deal,
        forecast=forecast,
        global_wr=round(global_wr * 100),
        avg_cycle=avg_cycle,
        pipeline_overdue=0,
    )


# ─────────────────────────────────────────────────────────────────
# LEAD JSON (modal pre-fill)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/<int:id>")
@login_required
def get_lead(id):
    lead = Lead.query.get_or_404(id)
    contact_history = []
    notes = []
    for n in lead.notes.order_by(LeadNote.created_at.desc()).limit(20).all():
        entry = {
            "id": n.id,
            "date": n.created_at.strftime("%b %d, %Y"),
            "who": n.user.display_name if n.user else "",
            "text": n.note_text,
            "user_id": n.user_id,
            "can_edit": n.user_id == current_user.id or current_user.is_admin,
        }
        if n.is_contact_log:
            contact_history.append(entry)
        else:
            notes.append(entry)
    return jsonify({
        "id": lead.id,
        "project_name": lead.project_name,
        "client": lead.client,
        "contact_name": lead.contact_name or "",
        "phone": lead.phone or "",
        "email": lead.email or "",
        "brand": lead.brand or "MPA",
        "status": lead.status,
        "stage": lead.stage or "",
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
        "contact_history": contact_history,
        "notes": notes,
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
    lead.stage = form.get("stage", "").strip() or None
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
    old_status = lead.status
    _apply_form_to_lead(lead, request.form)
    lead.updated_by = current_user.id

    # Inline note from lead modal
    note_inline = request.form.get("note_inline", "").strip()
    if note_inline:
        db.session.add(LeadNote(lead_id=lead.id, user_id=current_user.id, note_text=note_inline))

    changes = []
    if old_status != lead.status:
        changes.append(f"status → {lead.status}")
    msg = f"Updated lead: {lead.project_name}" + (f" ({', '.join(changes)})" if changes else "")

    db.session.add(ActivityLog(
        user_id=current_user.id, region=lead.region,
        entity_type="lead", entity_id=lead.id,
        action="updated", message=msg,
    ))
    db.session.commit()

    flash(f'Lead "{lead.project_name}" updated.', "success")
    return redirect(_safe_next(url_for("pipeline.index")))


# ─────────────────────────────────────────────────────────────────
# TOUCH / LOG CONTACT
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/lead/<int:id>/touch", methods=["POST"])
@login_required
def touch_lead(id):
    lead = Lead.query.get_or_404(id)
    data = request.get_json(silent=True) or {}
    note_text = (data.get("note") or request.form.get("note", "")).strip()
    next_action = (data.get("next_action") or request.form.get("next_action", "")).strip()
    follow_up_str = (data.get("follow_up") or request.form.get("follow_up", "")).strip()
    contact_date_str = (data.get("contact_date") or request.form.get("contact_date", "")).strip()

    if not note_text:
        if request.is_json:
            return jsonify({"ok": False, "error": "Note required"}), 400
        flash("Note is required.", "error")
        return redirect(url_for("pipeline.index"))

    # Update last contact date
    today_date = date.today()
    if contact_date_str:
        try:
            lead.last_contact = date.fromisoformat(contact_date_str)
        except ValueError:
            lead.last_contact = today_date
    else:
        lead.last_contact = today_date

    # Update follow-up date
    if follow_up_str:
        try:
            lead.follow_up = date.fromisoformat(follow_up_str)
        except ValueError:
            pass

    # Update next action
    if next_action:
        lead.next_action = next_action

    # Add note (marked as contact log so it shows in contact history, not notes)
    db.session.add(LeadNote(lead_id=lead.id, user_id=current_user.id, note_text=note_text, is_contact_log=True))

    # Audit log
    db.session.add(ActivityLog(
        user_id=current_user.id, region=lead.region,
        entity_type="lead", entity_id=lead.id,
        action="note", message=f"Contact logged: {note_text[:80]}",
    ))
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash("Contact logged.", "success")
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
    db.session.add(LeadNote(lead_id=lead.id, user_id=current_user.id, note_text=text, is_contact_log=False))
    db.session.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# EDIT NOTE (AJAX)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/note/<int:note_id>/edit", methods=["POST"])
@login_required
def edit_note(note_id):
    note = LeadNote.query.get_or_404(note_id)
    if not current_user.is_admin and note.user_id != current_user.id:
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Note cannot be empty"}), 400
    note.note_text = text
    db.session.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# DELETE NOTE (AJAX)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/note/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id):
    note = LeadNote.query.get_or_404(note_id)
    if not current_user.is_admin and note.user_id != current_user.id:
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    db.session.delete(note)
    db.session.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# COMPANY SEARCH (AJAX autocomplete)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/search/companies")
@login_required
def search_companies():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    like = f"%{q}%"
    # Search Company table first
    companies = Company.query.filter(Company.name.ilike(like)).limit(10).all()
    company_names_lower = {c.name.lower() for c in companies}
    results = [{"id": c.id, "name": c.name, "phone": c.phone or "", "email": c.email or ""} for c in companies]
    # Also surface distinct Lead.client values not already in Company table
    lead_rows = db.session.query(Lead.client).filter(
        Lead.client.ilike(like),
        Lead.client.isnot(None),
        Lead.client != "",
    ).distinct().limit(10).all()
    for r in lead_rows:
        if r[0] and r[0].lower() not in company_names_lower:
            results.append({"id": None, "name": r[0], "phone": "", "email": ""})
    results.sort(key=lambda x: x["name"])
    return jsonify({"results": results[:15]})


# ─────────────────────────────────────────────────────────────────
# CONTACT SEARCH (AJAX autocomplete)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/search/contacts")
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
            "company": c.company or "",
            "phone": c.phone or "",
            "email": c.email or "",
        }
        for c in contacts
    ]
    return jsonify({"results": results})


# ─────────────────────────────────────────────────────────────────
# CREATE CONTACT (AJAX)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/contact/create", methods=["POST"])
@login_required
def create_contact():
    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    name = f"{first_name} {last_name}".strip()
    if not name:
        return jsonify({"ok": False, "error": "First or last name required"}), 400
    company_id = data.get("company_id") or None
    company_text = (data.get("company") or "").strip() or None
    contact = Contact(
        first_name=first_name or None,
        last_name=last_name or None,
        name=name,
        company=company_text,
        company_id=company_id,
        position=(data.get("position") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify({
        "ok": True,
        "contact": {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone or "",
            "email": contact.email or "",
            "company": contact.company or "",
        },
    })


# ─────────────────────────────────────────────────────────────────
# CREATE COMPANY (AJAX)
# ─────────────────────────────────────────────────────────────────

@pipeline_bp.route("/company/create", methods=["POST"])
@login_required
def create_company():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Company name required"}), 400
    company = Company(
        name=name,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
    )
    db.session.add(company)
    db.session.commit()
    return jsonify({
        "ok": True,
        "company": {
            "id": company.id,
            "name": company.name,
            "phone": company.phone or "",
            "email": company.email or "",
        },
    })
