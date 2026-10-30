from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from services.db import db_cursor, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, admin_required, handle_db_error, require_fields

auth_bp = Blueprint("auth", __name__)


def is_inactive_employee_account(user):
    if (user.get("role") or "").lower() not in ("staff", "employee") or not user.get("business_id"):
        return False
    employee = fetch_one(
        """SELECT id FROM employees
           WHERE business_id = %s AND email IS NOT NULL AND LOWER(email) = LOWER(%s)
             AND LOWER(COALESCE(status, 'active')) != 'active'
           LIMIT 1""",
        (user["business_id"], user.get("email") or ""),
    )
    return bool(employee)


@auth_bp.post("/register")
def register_admin():
    data = request.get_json() or {}
    company_name = (data.get("company_name") or data.get("business_name") or "").strip()
    if not company_name:
        return jsonify({"error": "Company Name is required"}), 400

    error = require_fields(data, ["name", "email", "password"])
    if error:
        return jsonify({"error": error}), 400

    email = data["email"].strip().lower()

    try:
        existing = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
        if existing:
            return jsonify({"error": "Email is already registered"}), 409

        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO businesses (name, industry, business_type, phone, email, address)
                VALUES (%s, %s, %s, %s, %s, %s)
                """),
                (
                    company_name,
                    (data.get("industry") or "Manufacturing").strip(),
                    (data.get("business_type") or "Knitwear / Garment Manufacturing").strip(),
                    (data.get("business_phone") or "").strip() or None,
                    (data.get("business_email") or "").strip() or None,
                    (data.get("business_address") or "").strip() or None,
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
                    data["name"].strip(),
                    email,
                    generate_password_hash(data["password"]),
                    "admin",
                ),
            )
            user_id = cursor.lastrowid

        session["user_id"] = user_id
        session["business_id"] = business_id
        session["user_name"] = data["name"].strip()
        session["role"] = "admin"

        return jsonify({
            "message": "Business & Admin registered successfully",
            "user_id": user_id,
            "role": "admin",
            "business_name": company_name,
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

        # A portal account must be anchored to one exact, active customer record.
        matching_customers = fetch_all(
            """
            SELECT id, business_id FROM customers
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
              AND ((email IS NOT NULL AND LOWER(email) = %s)
               OR (%s != '' AND phone IS NOT NULL AND phone = %s))
              AND LOWER(COALESCE(status, 'active')) = 'active'
            """,
            (data["name"].strip(), email, phone, phone),
        )
        if len(matching_customers) != 1:
            return jsonify({"error": "Your account is not registered with this company. Please contact the administrator."}), 403

        customer = matching_customers[0]
        first_biz = customer["business_id"]

        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO users (business_id, name, email, phone, password_hash, role, is_active)
                VALUES (%s, %s, %s, %s, %s, 'customer', 1)
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

            cursor.execute(
                normalize_query("""
                INSERT INTO customer_users (user_id, business_id, customer_id)
                VALUES (%s, %s, %s)
                """),
                (user_id, customer["business_id"], customer["id"]),
            )

        session["user_id"] = user_id
        session["business_id"] = first_biz
        session["user_name"] = data["name"].strip()
        session["role"] = "customer"

        return jsonify({
            "message": "Customer account created successfully",
            "user_id": user_id,
            "role": "customer",
            "registered": True,
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
            "SELECT id, business_id, name, email, role, password_hash, is_active FROM users WHERE email = %s",
            (data["email"].strip().lower(),),
        )
        if not user or not check_password_hash(user["password_hash"], data["password"]):
            return jsonify({"error": "Invalid email or password"}), 401

        # Block inactive accounts from logging in
        is_active = user.get("is_active")
        if is_active is not None and int(is_active) == 0:
            return jsonify({"error": "Your account has been deactivated. Please contact the administrator."}), 403

        role = user.get("role") or "staff"
        if is_inactive_employee_account(user):
            return jsonify({"error": "Your employee account is inactive. Please contact the administrator."}), 403
        if role == "customer":
            link = fetch_one(
                """SELECT cu.business_id, cu.customer_id FROM customer_users cu
                   JOIN customers c ON c.id = cu.customer_id AND c.business_id = cu.business_id
                   WHERE cu.user_id = %s AND LOWER(COALESCE(c.status, 'active')) = 'active'
                   LIMIT 1""",
                (user["id"],),
            )
            if not link:
                return jsonify({"error": "Your account is not registered with this company. Please contact the administrator."}), 403
            user["business_id"] = link["business_id"]
            session.clear()
        session["user_id"] = user["id"]
        session["business_id"] = user["business_id"]
        session["user_name"] = user["name"]
        session["role"] = role

        biz_name = None
        if user.get("business_id"):
            biz = fetch_one("SELECT name FROM businesses WHERE id = %s", (user["business_id"],))
            if biz and biz.get("name"):
                biz_name = biz["name"].strip()

        if not biz_name and role != "customer":
            biz_name = "Aur Garments"

        redirect_page = "/pages/customer-portal.html" if role == "customer" else "/pages/dashboard.html"

        return jsonify({
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": role,
                "business_id": user["business_id"],
                "business_name": biz_name,
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

    user = fetch_one("SELECT id, role, business_id, name, is_active FROM users WHERE id = %s", (session["user_id"],))
    if not user or not user.get("is_active", 1):
        session.clear()
        return jsonify({"authenticated": False, "error": "Your account has been deactivated. Please contact the administrator."}), 403
    role = user.get("role") or "staff"
    if is_inactive_employee_account(user):
        session.clear()
        return jsonify({"authenticated": False, "error": "Your employee account is inactive. Please contact the administrator."}), 403
    session["role"] = role
    session["business_id"] = user.get("business_id")
    session["user_name"] = user.get("name")
    biz_name = None
    biz_id = user.get("business_id")
    if biz_id:
        biz = fetch_one("SELECT name FROM businesses WHERE id = %s", (biz_id,))
        if biz and biz.get("name"):
            biz_name = biz["name"].strip()

    if not biz_name and role != "customer":
        biz_name = "Aur Garments"

    # Revalidate the customer link on every session check, including deactivation.
    registered = True
    if role == "customer":
        user_id = session["user_id"]
        linked = fetch_one(
            """SELECT COUNT(*) AS cnt FROM customer_users cu
               JOIN customers c ON c.id = cu.customer_id AND c.business_id = cu.business_id
               WHERE cu.user_id = %s AND LOWER(COALESCE(c.status, 'active')) = 'active'""",
            (user_id,),
        )
        registered = bool(linked and linked.get("cnt", 0) > 0)
        if not registered:
            session.clear()
            return jsonify({"authenticated": False, "error": "Your account is not registered with this company. Please contact the administrator."}), 403

    return jsonify({
        "authenticated": True,
        "user": {
            "id": user["id"],
            "business_id": user.get("business_id"),
            "business_name": biz_name,
            "name": user.get("name"),
            "role": role,
            "registered": registered,
        },
    })


@auth_bp.post("/update-business")
@admin_required
def update_business():
    if not session.get("user_id"):
        return jsonify({"error": "Authentication required"}), 401

    biz_id = session.get("business_id")
    if not biz_id:
        return jsonify({"error": "No associated business found for account"}), 400

    data = request.get_json() or {}
    company_name = (data.get("company_name") or data.get("name") or data.get("business_name") or "").strip()
    if not company_name:
        return jsonify({"error": "Company Name cannot be empty"}), 400

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                UPDATE businesses
                SET name = %s,
                    gstin = %s,
                    phone = %s,
                    email = %s,
                    address = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """),
                (
                    company_name,
                    (data.get("gstin") or "").strip() or None,
                    (data.get("phone") or "").strip() or None,
                    (data.get("email") or "").strip() or None,
                    (data.get("address") or "").strip() or None,
                    biz_id,
                ),
            )

        return jsonify({
            "message": "Business profile updated successfully",
            "business_name": company_name,
        })
    except Exception:
        # Fallback if gstin column is not present in businesses table
        try:
            with db_cursor(commit=True) as cursor:
                cursor.execute(
                    normalize_query("""
                    UPDATE businesses
                    SET name = %s,
                        phone = %s,
                        email = %s,
                        address = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """),
                    (
                        company_name,
                        (data.get("phone") or "").strip() or None,
                        (data.get("email") or "").strip() or None,
                        (data.get("address") or "").strip() or None,
                        biz_id,
                    ),
                )
            return jsonify({
                "message": "Business profile updated successfully",
                "business_name": company_name,
            })
        except DatabaseError as exc:
            return handle_db_error(exc)

