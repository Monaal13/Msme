from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from services.db import db_cursor, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, handle_db_error, require_fields

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register_admin():
    data = request.get_json() or {}
    error = require_fields(data, ["business_name", "name", "email", "password"])
    if error:
        return jsonify({"error": error}), 400

    try:
        existing = fetch_one("SELECT id FROM users WHERE email = %s", (data["email"],))
        if existing:
            return jsonify({"error": "Email is already registered"}), 409

        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO businesses (name, industry, business_type, phone, email, address)
                VALUES (%s, %s, %s, %s, %s, %s)
                """),
                (
                    data["business_name"],
                    data.get("industry") or "Manufacturing",
                    data.get("business_type") or "Knitwear / Garment Manufacturing",
                    data.get("business_phone"),
                    data.get("business_email"),
                    data.get("business_address"),
                ),
            )
            business_id = cursor.lastrowid

            cursor.execute(
                normalize_query("""
                INSERT INTO users (business_id, name, email, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
                """),
                (
                    business_id,
                    data["name"],
                    data["email"],
                    generate_password_hash(data["password"]),
                    "admin",
                ),
            )
            user_id = cursor.lastrowid

        session["user_id"] = user_id
        session["business_id"] = business_id
        session["user_name"] = data["name"]
        session["role"] = "admin"

        return jsonify({
            "message": "Business & Admin registered successfully",
            "user_id": user_id,
            "role": "admin",
            "redirect": "/pages/dashboard.html",
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@auth_bp.post("/register-customer")
def register_customer():
    data = request.get_json() or {}
    error = require_fields(data, ["name", "email", "password"])
    if error:
        return jsonify({"error": error}), 400

    email = data["email"].strip().lower()
    phone = (data.get("phone") or "").strip()

    try:
        existing = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
        if existing:
            return jsonify({"error": "Email is already registered. Please login instead."}), 409

        matching_customers = fetch_all(
            """
            SELECT id, business_id FROM customers
            WHERE (email IS NOT NULL AND LOWER(email) = %s)
               OR (%s != '' AND phone IS NOT NULL AND phone = %s)
            """,
            (email, phone, phone),
        )

        first_biz = matching_customers[0]["business_id"] if matching_customers else None
        if not first_biz:
            biz_row = fetch_one("SELECT id FROM businesses ORDER BY id ASC LIMIT 1")
            first_biz = biz_row["id"] if biz_row else None

        if not first_biz:
            # Fallback create system business container
            first_biz = execute("INSERT INTO businesses (name, industry) VALUES ('Default Platform Store', 'Garments')")

        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO users (business_id, name, email, phone, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, 'customer')
                """),
                (
                    first_biz,
                    data["name"].strip(),
                    email,
                    phone or None,
                    generate_password_hash(data["password"]),
                ),
            )
            user_id = cursor.lastrowid

            for cust_rec in matching_customers:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO customer_users (user_id, business_id, customer_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(user_id, business_id) DO NOTHING
                    """),
                    (user_id, cust_rec["business_id"], cust_rec["id"]),
                )

        session["user_id"] = user_id
        session["business_id"] = 0
        session["user_name"] = data["name"].strip()
        session["role"] = "customer"

        return jsonify({
            "message": "Customer account created successfully",
            "user_id": user_id,
            "role": "customer",
            "redirect": "/pages/customer-portal.html",
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    error = require_fields(data, ["email", "password"])
    if error:
        return jsonify({"error": error}), 400

    try:
        user = fetch_one(
            "SELECT id, business_id, name, email, role, password_hash FROM users WHERE email = %s",
            (data["email"].strip().lower(),),
        )
        if not user or not check_password_hash(user["password_hash"], data["password"]):
            return jsonify({"error": "Invalid email or password"}), 401

        role = user.get("role") or "staff"
        session["user_id"] = user["id"]
        session["business_id"] = user["business_id"]
        session["user_name"] = user["name"]
        session["role"] = role

        redirect_page = "/pages/customer-portal.html" if role == "customer" else "/pages/dashboard.html"

        return jsonify({
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": role,
                "business_id": user["business_id"],
            },
            "redirect": redirect_page,
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@auth_bp.get("/me")
def me():
    if not session.get("user_id"):
        return jsonify({"authenticated": False}), 401

    biz_name = None
    biz_id = session.get("business_id")
    if biz_id:
        biz = fetch_one("SELECT name FROM businesses WHERE id = %s", (biz_id,))
        if biz:
            biz_name = biz["name"]

    return jsonify({
        "authenticated": True,
        "user": {
            "id": session["user_id"],
            "business_id": session.get("business_id"),
            "business_name": biz_name,
            "name": session.get("user_name"),
            "role": session.get("role", "staff"),
        },
    })
