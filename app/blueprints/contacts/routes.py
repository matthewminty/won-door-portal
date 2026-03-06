"""Contacts Blueprint — Address book for People and Companies"""
import csv
import io
from flask import (
    Blueprint, render_template, request, jsonify, session, Response,
)
from flask_login import login_required, current_user
from sqlalchemy import or_

from app import db
from app.models import Company, Contact, ContactLink, Job, Lead, PicklistItem

contacts_bp = Blueprint("contacts", __name__)


@contacts_bp.route("/")
@login_required
def index():
    active_region = session.get("region", current_user.default_region)
    tab = request.args.get("tab", "people")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    regions = [r.value for r in PicklistItem.query.filter_by(category="contact_region").order_by(PicklistItem.sort_order, PicklistItem.value).all()]

    return render_template(
        "contacts/index.html",
        tab=tab,
        q=q,
        page=page,
        per_page=per_page,
        active_region=active_region,
        regions=regions,
    )


# ─────────────────────────────────────────────────────────────────
# PEOPLE API (JSON)
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/api/people")
@login_required
def api_people():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")

    query = Contact.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Contact.name.ilike(like),
            Contact.email.ilike(like),
            Contact.phone.ilike(like),
            Contact.company.ilike(like),
        ))
    col_map = {
        "name": Contact.name,
        "company": Contact.company,
        "position": Contact.position,
        "email": Contact.email,
        "region": Contact.region,
    }
    col = col_map.get(sort, Contact.name)
    query = query.order_by(col.asc() if order == "asc" else col.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    results = []
    for c in pagination.items:
        results.append({
            "id": c.id,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
            "name": c.name,
            "company": c.company or "",
            "company_id": c.company_id,
            "company_name": c.linked_company.name if c.linked_company else (c.company or ""),
            "position": c.position or "",
            "email": c.email or "",
            "phone": c.phone or "",
            "address": c.address or "",
            "region": c.region or "",
        })
    return jsonify({
        "results": results,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "sort": sort,
        "order": order,
    })


# ─────────────────────────────────────────────────────────────────
# COMPANIES API (JSON)
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/api/companies")
@login_required
def api_companies():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")

    query = Company.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Company.name.ilike(like),
            Company.email.ilike(like),
            Company.phone.ilike(like),
        ))
    col_map = {
        "name": Company.name,
        "email": Company.email,
        "address": Company.address,
    }
    col = col_map.get(sort, Company.name)
    query = query.order_by(col.asc() if order == "asc" else col.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    results = []
    for co in pagination.items:
        results.append({
            "id": co.id,
            "name": co.name,
            "phone": co.phone or "",
            "email": co.email or "",
            "address": co.address or "",
            "contact_count": len(co.contacts),
        })
    return jsonify({
        "results": results,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "sort": sort,
        "order": order,
    })


# ─────────────────────────────────────────────────────────────────
# CREATE / EDIT / DELETE — PEOPLE
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/api/person/create", methods=["POST"])
@login_required
def create_person():
    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    name = f"{first_name} {last_name}".strip()
    if not name:
        return jsonify({"ok": False, "error": "Name is required"}), 400
    company_id = data.get("company_id") or None
    contact = Contact(
        first_name=first_name or None,
        last_name=last_name or None,
        name=name,
        company=(data.get("company") or "").strip() or None,
        company_id=company_id,
        position=(data.get("position") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
        region=(data.get("region") or "").strip() or None,
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify({"ok": True, "id": contact.id})


@contacts_bp.route("/api/person/<int:person_id>/edit", methods=["POST"])
@login_required
def edit_person(person_id):
    contact = Contact.query.get_or_404(person_id)
    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    name = f"{first_name} {last_name}".strip()
    if not name:
        return jsonify({"ok": False, "error": "Name is required"}), 400
    contact.first_name = first_name or None
    contact.last_name = last_name or None
    contact.name = name
    contact.company = (data.get("company") or "").strip() or None
    contact.company_id = data.get("company_id") or None
    contact.position = (data.get("position") or "").strip() or None
    contact.phone = (data.get("phone") or "").strip() or None
    contact.email = (data.get("email") or "").strip() or None
    contact.address = (data.get("address") or "").strip() or None
    contact.region = (data.get("region") or "").strip() or None
    db.session.commit()
    return jsonify({"ok": True})


@contacts_bp.route("/api/person/<int:person_id>/delete", methods=["POST"])
@login_required
def delete_person(person_id):
    contact = Contact.query.get_or_404(person_id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"ok": True})


@contacts_bp.route("/api/person/<int:person_id>")
@login_required
def get_person(person_id):
    c = Contact.query.get_or_404(person_id)
    links = ContactLink.query.filter_by(contact_id=c.id).all()
    linked_leads = []
    linked_jobs = []
    for lk in links:
        if lk.lead_id:
            lead = db.session.get(Lead, lk.lead_id)
            if lead:
                linked_leads.append({
                    "id": lead.id, "name": lead.project_name,
                    "status": lead.status, "value": lead.value or 0,
                })
        if lk.job_id:
            job = db.session.get(Job, lk.job_id)
            if job:
                linked_jobs.append({
                    "id": job.id, "number": job.job_number,
                    "name": job.job_name, "status": job.status,
                })
    return jsonify({
        "id": c.id,
        "first_name": c.first_name or "",
        "last_name": c.last_name or "",
        "name": c.name,
        "company": c.company or "",
        "company_id": c.company_id,
        "company_name": c.linked_company.name if c.linked_company else (c.company or ""),
        "position": c.position or "",
        "email": c.email or "",
        "phone": c.phone or "",
        "address": c.address or "",
        "region": c.region or "",
        "linked_leads": linked_leads,
        "linked_jobs": linked_jobs,
    })


# ─────────────────────────────────────────────────────────────────
# CREATE / EDIT / DELETE — COMPANIES
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/api/company/create", methods=["POST"])
@login_required
def create_company():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Company name is required"}), 400
    company = Company(
        name=name,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
    )
    db.session.add(company)
    db.session.commit()
    return jsonify({"ok": True, "id": company.id})


@contacts_bp.route("/api/company/<int:company_id>/edit", methods=["POST"])
@login_required
def edit_company(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Company name is required"}), 400
    company.name = name
    company.phone = (data.get("phone") or "").strip() or None
    company.email = (data.get("email") or "").strip() or None
    company.address = (data.get("address") or "").strip() or None
    db.session.commit()
    return jsonify({"ok": True})


@contacts_bp.route("/api/company/<int:company_id>/delete", methods=["POST"])
@login_required
def delete_company(company_id):
    company = Company.query.get_or_404(company_id)
    # Unlink contacts first
    for c in company.contacts:
        c.company_id = None
    db.session.delete(company)
    db.session.commit()
    return jsonify({"ok": True})


@contacts_bp.route("/api/company/<int:company_id>")
@login_required
def get_company(company_id):
    co = Company.query.get_or_404(company_id)
    people = Contact.query.filter_by(company_id=co.id).order_by(Contact.name).all()
    # Gather linked leads across all contacts in this company
    company_lead_ids = set()
    for person in people:
        for lk in ContactLink.query.filter_by(contact_id=person.id).all():
            if lk.lead_id:
                company_lead_ids.add(lk.lead_id)
    linked_leads = []
    for lead_id in list(company_lead_ids)[:5]:
        lead = db.session.get(Lead, lead_id)
        if lead:
            linked_leads.append({
                "id": lead.id, "name": lead.project_name,
                "status": lead.status, "value": lead.value or 0,
            })
    return jsonify({
        "id": co.id,
        "name": co.name,
        "phone": co.phone or "",
        "email": co.email or "",
        "address": co.address or "",
        "contacts": [
            {"id": c.id, "name": c.name, "position": c.position or "", "phone": c.phone or "", "email": c.email or ""}
            for c in people
        ],
        "linked_leads": linked_leads,
    })


# ─────────────────────────────────────────────────────────────────
# SEARCH COMPANIES (for autocomplete in person forms)
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/api/search/companies")
@login_required
def search_companies():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    companies = Company.query.filter(Company.name.ilike(f"%{q}%")).limit(10).all()
    return jsonify({
        "results": [{"id": c.id, "name": c.name} for c in companies],
    })


# ─────────────────────────────────────────────────────────────────
# EXPORT CSV
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/export/people")
@login_required
def export_people():
    contacts = Contact.query.order_by(Contact.name).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "first_name", "last_name", "name", "company", "position", "email", "phone", "address", "region"])
    for c in contacts:
        writer.writerow([
            c.id, c.first_name or "", c.last_name or "", c.name,
            c.linked_company.name if c.linked_company else (c.company or ""),
            c.position or "", c.email or "", c.phone or "", c.address or "", c.region or "",
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=people.csv"},
    )


@contacts_bp.route("/export/companies")
@login_required
def export_companies():
    companies = Company.query.order_by(Company.name).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "phone", "email", "address", "contact_count"])
    for co in companies:
        writer.writerow([co.id, co.name, co.phone or "", co.email or "", co.address or "", len(co.contacts)])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=companies.csv"},
    )


# ─────────────────────────────────────────────────────────────────
# IMPORT CSV
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/import/people", methods=["POST"])
@login_required
def import_people():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    try:
        text = f.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        created = updated = 0
        errors = []
        for i, row in enumerate(reader, start=2):
            first = (row.get("first_name") or "").strip()
            last = (row.get("last_name") or "").strip()
            name = (row.get("name") or f"{first} {last}").strip()
            if not name:
                errors.append(f"Row {i}: name is required")
                continue
            email = (row.get("email") or "").strip().lower() or None
            existing = Contact.query.filter_by(email=email).first() if email else None
            if existing:
                existing.name = name
                existing.first_name = first or None
                existing.last_name = last or None
                existing.position = (row.get("position") or "").strip() or existing.position
                existing.phone = (row.get("phone") or "").strip() or existing.phone
                existing.address = (row.get("address") or "").strip() or existing.address
                existing.region = (row.get("region") or "").strip() or existing.region
                updated += 1
            else:
                db.session.add(Contact(
                    first_name=first or None, last_name=last or None, name=name,
                    email=email,
                    phone=(row.get("phone") or "").strip() or None,
                    position=(row.get("position") or "").strip() or None,
                    address=(row.get("address") or "").strip() or None,
                    region=(row.get("region") or "").strip() or None,
                    company=(row.get("company") or "").strip() or None,
                ))
                created += 1
        db.session.commit()
        return jsonify({"ok": True, "created": created, "updated": updated, "errors": errors})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


@contacts_bp.route("/import/companies", methods=["POST"])
@login_required
def import_companies():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    try:
        text = f.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        created = updated = 0
        errors = []
        for i, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            if not name:
                errors.append(f"Row {i}: name is required")
                continue
            existing = Company.query.filter(Company.name.ilike(name)).first()
            if existing:
                existing.phone = (row.get("phone") or "").strip() or existing.phone
                existing.email = (row.get("email") or "").strip() or existing.email
                existing.address = (row.get("address") or "").strip() or existing.address
                updated += 1
            else:
                db.session.add(Company(
                    name=name,
                    phone=(row.get("phone") or "").strip() or None,
                    email=(row.get("email") or "").strip() or None,
                    address=(row.get("address") or "").strip() or None,
                ))
                created += 1
        db.session.commit()
        return jsonify({"ok": True, "created": created, "updated": updated, "errors": errors})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


# ─────────────────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────────────────

@contacts_bp.route("/api/analytics")
@login_required
def api_analytics():
    from sqlalchemy import func as sqlfunc
    links = ContactLink.query.filter(ContactLink.lead_id.isnot(None)).all()
    lead_ids = list({lk.lead_id for lk in links})
    if lead_ids:
        rows = db.session.query(
            sqlfunc.count(Lead.id),
            sqlfunc.sum(Lead.value),
            sqlfunc.sum(db.case((Lead.status == "Won", Lead.value), else_=0)),
            sqlfunc.count(db.case((Lead.status.in_(["Hot", "Long Burn"]), Lead.id))),
        ).filter(Lead.id.in_(lead_ids)).one()
        total_leads, total_pipeline, total_won, active_count = rows
    else:
        total_leads = total_pipeline = total_won = active_count = 0
    return jsonify({
        "total_linked_leads": int(total_leads or 0),
        "total_pipeline_value": float(total_pipeline or 0),
        "total_won_value": float(total_won or 0),
        "active_lead_count": int(active_count or 0),
    })
