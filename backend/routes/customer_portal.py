from flask import Blueprint, jsonify, request, session

from services.db import fetch_all, fetch_one
from .common import DatabaseError, handle_db_error, login_required

customer_portal_bp = Blueprint("customer_portal", __name__)


def current_customer_info():
    user_id = session.get("user_id")
    if not user_id:
        return None, None
    user = fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not user or user.get("role") != "customer":
        return None, None
    return user_id, user


@customer_portal_bp.get("/stores")
@login_required
def customer_stores():
    user_id = session.get("user_id")
    try:
        stores = fetch_all(
            """
            SELECT b.id AS business_id, b.name AS business_name, b.industry, b.phone, b.email, b.address,
                   c.id AS customer_id, c.name AS customer_name,
                   (SELECT COUNT(*) FROM production_orders WHERE customer_id = c.id AND business_id = b.id) AS total_orders,
                   (SELECT COUNT(*) FROM sales WHERE customer_id = c.id AND business_id = b.id) AS total_bills
            FROM customer_users cu
            JOIN businesses b ON b.id = cu.business_id
            JOIN customers c ON c.id = cu.customer_id
            WHERE cu.user_id = %s
            ORDER BY b.name ASC
            """,
            (user_id,),
        )
        return jsonify(stores)
    except DatabaseError as exc:
        return handle_db_error(exc)


@customer_portal_bp.get("/orders")
@login_required
def customer_orders():
    user_id = session.get("user_id")
    biz_id_param = request.args.get("business_id")
    try:
        query = """
            SELECT po.*, b.name AS business_name, b.phone AS business_phone
            FROM production_orders po
            JOIN customer_users cu ON cu.business_id = po.business_id AND cu.customer_id = po.customer_id
            JOIN businesses b ON b.id = po.business_id
            WHERE cu.user_id = %s
        """
        params = [user_id]
        if biz_id_param:
            query += " AND po.business_id = %s"
            params.append(biz_id_param)

        query += " ORDER BY po.created_at DESC"
        orders = fetch_all(query, tuple(params))

        # Attach progress percentage based on stage
        stage_percentages = {
            "New": 10,
            "Cutting": 25,
            "Stitching": 45,
            "Finishing": 65,
            "Quality Check": 80,
            "Packing": 90,
            "Ready for Dispatch": 95,
            "Completed": 100,
        }

        for ord_item in orders:
            st = ord_item.get("current_stage") or "New"
            ord_item["progress_percent"] = stage_percentages.get(st, 10)

        return jsonify(orders)
    except DatabaseError as exc:
        return handle_db_error(exc)


@customer_portal_bp.get("/invoices")
@login_required
def customer_invoices():
    user_id = session.get("user_id")
    biz_id_param = request.args.get("business_id")
    try:
        query = """
            SELECT s.*, b.name AS business_name, b.phone AS business_phone, b.email AS business_email
            FROM sales s
            JOIN customer_users cu ON cu.business_id = s.business_id AND cu.customer_id = s.customer_id
            JOIN businesses b ON b.id = s.business_id
            WHERE cu.user_id = %s
        """
        params = [user_id]
        if biz_id_param:
            query += " AND s.business_id = %s"
            params.append(biz_id_param)

        query += " ORDER BY s.sale_date DESC"
        sales = fetch_all(query, tuple(params))
        return jsonify(sales)
    except DatabaseError as exc:
        return handle_db_error(exc)


@customer_portal_bp.get("/notifications")
@login_required
def customer_notifications():
    user_id = session.get("user_id")
    try:
        messages = fetch_all(
            """
            SELECT m.*, b.name AS business_name
            FROM messages m
            JOIN customer_users cu ON cu.business_id = m.business_id AND cu.customer_id = m.customer_id
            JOIN businesses b ON b.id = m.business_id
            WHERE cu.user_id = %s AND LOWER(m.status) IN ('sent', 'scheduled')
            ORDER BY m.created_at DESC
            """,
            (user_id,),
        )
        return jsonify(messages)
    except DatabaseError as exc:
        return handle_db_error(exc)


@customer_portal_bp.get("/profile")
@login_required
def customer_profile():
    user_id = session.get("user_id")
    try:
        user = fetch_one("SELECT id, name, email, phone, role, created_at FROM users WHERE id = %s", (user_id,))
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user)
    except DatabaseError as exc:
        return handle_db_error(exc)
