"""Contacts Blueprint — Address book for People and Companies"""
from flask import (
    Blueprint, render_template, request, jsonify, session,
)
from flask_login import login_required, current_user
from sqlalchemy import or_

from app import db
from app.models import Company, Contact

contacts_bp = Blueprint("contacts", __name__)


@contacts_bp.route("/")
@login_required
def index():
    active_region = session.get("region", current_user.default_region)
    tab = request.args.get("tab", "people")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    return render_template(
        "contacts/index.html",
        tab=tab,
        q=q,
        page=page,
        per_page=per_page,
        active_region=active_region,
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

    query = Contact.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Contact.name.ilike(like),
            Contact.email.ilike(like),
            Contact.phone.ilike(like),
            Contact.company.ilike(like),
        ))
    query = query.order_by(Contact.name.asc())
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
        })
    return jsonify({
        "results": results,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
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

    query = Company.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Company.name.ilike(like),
            Company.email.ilike(like),
            Company.phone.ilike(like),
        ))
    query = query.order_by(Company.name.asc())
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
