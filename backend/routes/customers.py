import re
from flask import Blueprint, jsonify, request

from services.db import execute, fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

customers_bp = Blueprint("customers", __name__)


def validate_customer_data(data):
    name = (data.get("name") or "").strip()
    if not name:
        return "Customer name is required"
    email = (data.get("email") or "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return "Invalid email address format"
    phone = (data.get("phone") or "").strip()
    if phone and not re.match(r"^[0-9+\-\s()]{7,15}$", phone):
        return "Invalid phone number format"
    return None


@customers_bp.get("")
@login_required
def list_customers():
    search = f"%{request.args.get('search', '').strip()}%"
    try:
        customers = fetch_all(
            """
            SELECT c.*,
                   COUNT(s.id) AS total_orders,
                   COALESCE(SUM(s.total_amount), 0) AS total_purchase,
                   COALESCE(SUM(CASE WHEN LOWER(s.payment_status) = 'paid' THEN s.total_amount ELSE 0 END), 0) AS total_paid,
                   COALESCE(SUM(CASE WHEN LOWER(s.payment_status) != 'paid' THEN s.total_amount ELSE 0 END), 0) AS total_pending,
                   MAX(s.payment_date) AS last_payment_date,
                   MAX(s.sale_date) AS last_purchase_date
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id AND s.business_id = c.business_id
            WHERE c.business_id = %s
              AND (c.name LIKE %s OR c.phone LIKE %s OR c.email LIKE %s OR c.company_name LIKE %s)
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            (current_business_id(), search, search, search, search),
        )
        return jsonify(customers)
    except DatabaseError as exc:
        return handle_db_error(exc)


@customers_bp.post("")
@login_required
def create_customer():
    data = request.get_json() or {}
    error = validate_customer_data(data)
    if error:
        return jsonify({"error": error}), 400
    try:
        customer_id = execute(
            """
            INSERT INTO customers (business_id, name, phone, email, address, company_name, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                current_business_id(),
                data["name"].strip(),
                data.get("phone", "").strip() or None,
                data.get("email", "").strip() or None,
                data.get("address", "").strip() or None,
                data.get("company_name", "").strip() or None,
                (data.get("status") or "active").strip().lower(),
            ),
        )
        return jsonify({"message": "Customer created", "id": customer_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@customers_bp.get("/<int:customer_id>")
@login_required
def get_customer(customer_id):
    biz_id = current_business_id()
    try:
        customer = fetch_one(
            """
            SELECT c.*,
                   COUNT(s.id) AS total_orders,
                   COALESCE(SUM(s.total_amount), 0) AS total_purchase,
                   COALESCE(SUM(CASE WHEN LOWER(s.payment_status) = 'paid' THEN s.total_amount ELSE 0 END), 0) AS total_paid,
                   COALESCE(SUM(CASE WHEN LOWER(s.payment_status) != 'paid' THEN s.total_amount ELSE 0 END), 0) AS total_pending,
                   MAX(s.payment_date) AS last_payment_date,
                   MAX(s.sale_date) AS last_purchase_date
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id AND s.business_id = c.business_id
            WHERE c.id = %s AND c.business_id = %s
            GROUP BY c.id
            """,
            (customer_id, biz_id),
        )
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        history = fetch_all(
            """
            SELECT id, invoice_number, total_amount, sale_date, payment_status, payment_date, due_date
            FROM sales
            WHERE customer_id = %s AND business_id = %s
            ORDER BY sale_date DESC, id DESC
            """,
            (customer_id, biz_id),
        )
        customer["purchase_history"] = history

        # Fetch message history
        message_history = fetch_all(
            """
            SELECT id, type, message_text, channel, status, scheduled_at, sent_at, created_at, error_message, updated_at
            FROM messages
            WHERE customer_id = %s AND business_id = %s
            ORDER BY created_at DESC
            """,
            (customer_id, biz_id),
        )
        customer["message_history"] = message_history

        # Build customer timeline dynamically
        timeline = []
        for sale in history:
            timeline.append({
                "type": "purchase",
                "label": f"Purchase — ₹{sale['total_amount']:,.0f}",
                "date": sale["sale_date"],
                "sub": f"Invoice: {sale['invoice_number'] or ('INV-' + str(sale['id']))}"
            })

        for msg in message_history:
            t_label = msg["type"].replace("_", " ").title()
            if msg["status"] == "sent":
                timeline.append({
                    "type": "message_sent",
                    "label": f"{t_label} confirmation sent" if msg["type"] == "purchase" else f"{t_label} sent",
                    "date": msg["sent_at"] or msg["created_at"],
                    "sub": f"Channel: {msg['channel']}"
                })
            elif msg["status"] == "scheduled":
                timeline.append({
                    "type": "message_scheduled",
                    "label": f"{t_label} scheduled",
                    "date": msg["scheduled_at"] or msg["created_at"],
                    "sub": f"Scheduled for {msg['scheduled_at']}"
                })
            elif msg["status"] == "failed":
                timeline.append({
                    "type": "message_failed",
                    "label": f"{t_label} failed",
                    "date": msg["updated_at"] or msg["created_at"],
                    "sub": msg["error_message"] or "Delivery failed"
                })

        # Sort timeline descending (latest first)
        timeline.sort(key=lambda x: x["date"] or "", reverse=True)
        customer["timeline"] = timeline

        return jsonify(customer)
    except DatabaseError as exc:
        return handle_db_error(exc)


@customers_bp.put("/<int:customer_id>")
@login_required
def update_customer(customer_id):
    data = request.get_json() or {}
    error = validate_customer_data(data)
    if error:
        return jsonify({"error": error}), 400
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM customers WHERE id = %s AND business_id = %s", (customer_id, biz_id))
        if not existing:
            return jsonify({"error": "Customer not found"}), 404

        execute(
            """
            UPDATE customers
            SET name = %s, phone = %s, email = %s, address = %s, company_name = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                data["name"].strip(),
                data.get("phone", "").strip() or None,
                data.get("email", "").strip() or None,
                data.get("address", "").strip() or None,
                data.get("company_name", "").strip() or None,
                (data.get("status") or "active").strip().lower(),
                customer_id,
                biz_id,
            ),
        )
        return jsonify({"message": "Customer updated"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@customers_bp.delete("/<int:customer_id>")
@login_required
def delete_customer(customer_id):
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM customers WHERE id = %s AND business_id = %s", (customer_id, biz_id))
        if not existing:
            return jsonify({"error": "Customer not found"}), 404

        sales_count = fetch_one(
            "SELECT COUNT(*) AS count FROM sales WHERE customer_id = %s AND business_id = %s",
            (customer_id, biz_id),
        )["count"]
        if sales_count > 0:
            return jsonify({
                "error": f"Cannot delete customer. This customer has {sales_count} existing sale/invoice record(s). Invoices must be preserved for accounting integrity."
            }), 400

        execute("DELETE FROM customers WHERE id = %s AND business_id = %s", (customer_id, biz_id))
        return jsonify({"message": "Customer deleted"})
    except DatabaseError as exc:
        return handle_db_error(exc)

