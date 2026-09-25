from flask import Blueprint, jsonify, request

from services.db import db_cursor, execute, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, current_business_id, handle_db_error, login_required

dispatches_bp = Blueprint("dispatches", __name__)


@dispatches_bp.get("")
@login_required
def list_dispatches():
    search = f"%{request.args.get('search', '').strip()}%"
    biz_id = current_business_id()
    try:
        dispatches = fetch_all(
            """
            SELECT d.*, c.name AS customer_name, c.company_name AS customer_company, c.phone AS customer_phone,
                   po.order_number, po.garment_name
            FROM dispatches d
            JOIN customers c ON c.id = d.customer_id AND c.business_id = d.business_id
            LEFT JOIN production_orders po ON po.id = d.production_order_id AND po.business_id = d.business_id
            WHERE d.business_id = %s
              AND (c.name LIKE %s OR po.order_number LIKE %s OR d.tracking_number LIKE %s OR d.courier_transport_details LIKE %s)
            ORDER BY d.dispatch_date DESC, d.id DESC
            """,
            (biz_id, search, search, search, search),
        )
        return jsonify(dispatches)
    except DatabaseError as exc:
        return handle_db_error(exc)


@dispatches_bp.post("")
@login_required
def create_dispatch():
    data = request.get_json() or {}
    biz_id = current_business_id()

    customer_id = data.get("customer_id")
    order_id = data.get("production_order_id")

    if not customer_id and order_id:
        ord_rec = fetch_one("SELECT customer_id FROM production_orders WHERE id = %s AND business_id = %s", (order_id, biz_id))
        if ord_rec:
            customer_id = ord_rec["customer_id"]

    if not customer_id:
        return jsonify({"error": "Customer is required for dispatch"}), 400

    try:
        quantity = int(data.get("quantity", 1))
        if quantity <= 0:
            return jsonify({"error": "Dispatch quantity must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid quantity format"}), 400

    dispatch_status = (data.get("status") or "Dispatched").strip()

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO dispatches (business_id, production_order_id, sale_id, customer_id, quantity, dispatch_date, courier_transport_details, tracking_number, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """),
                (
                    biz_id,
                    order_id or None,
                    data.get("sale_id") or None,
                    customer_id,
                    quantity,
                    data.get("dispatch_date") or None,
                    (data.get("courier_transport_details") or "").strip() or None,
                    (data.get("tracking_number") or "").strip() or None,
                    dispatch_status,
                    (data.get("notes") or "").strip() or None,
                ),
            )
            dispatch_id = cursor.lastrowid

            if order_id:
                new_stage = "Completed" if dispatch_status.lower() == "delivered" else "Completed"
                cursor.execute(
                    normalize_query("UPDATE production_orders SET current_stage = %s, status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s"),
                    (new_stage, dispatch_status, order_id, biz_id),
                )

        return jsonify({
            "message": "Dispatch record created successfully",
            "id": dispatch_id,
            "status": dispatch_status,
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@dispatches_bp.put("/<int:dispatch_id>")
@login_required
def update_dispatch(dispatch_id):
    data = request.get_json() or {}
    biz_id = current_business_id()
    new_status = (data.get("status") or "").strip()

    try:
        existing = fetch_one("SELECT * FROM dispatches WHERE id = %s AND business_id = %s", (dispatch_id, biz_id))
        if not existing:
            return jsonify({"error": "Dispatch record not found"}), 404

        execute(
            """
            UPDATE dispatches
            SET status = COALESCE(%s, status), tracking_number = COALESCE(%s, tracking_number),
                courier_transport_details = COALESCE(%s, courier_transport_details), notes = COALESCE(%s, notes), updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                new_status or None,
                (data.get("tracking_number") or "").strip() or None,
                (data.get("courier_transport_details") or "").strip() or None,
                (data.get("notes") or "").strip() or None,
                dispatch_id,
                biz_id,
            ),
        )
        return jsonify({"message": "Dispatch record updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)
