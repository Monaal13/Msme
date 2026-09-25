from flask import Blueprint, jsonify, request

from services.db import db_cursor, execute, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, current_business_id, handle_db_error, login_required

purchases_bp = Blueprint("purchases", __name__)


# ----------------------------------------------------
# SUPPLIER MANAGEMENT
# ----------------------------------------------------
@purchases_bp.get("/suppliers")
@login_required
def list_suppliers():
    search = f"%{request.args.get('search', '').strip()}%"
    biz_id = current_business_id()
    try:
        suppliers = fetch_all(
            """
            SELECT s.*, COUNT(p.id) AS total_purchases, COALESCE(SUM(p.total_amount), 0) AS total_spent
            FROM suppliers s
            LEFT JOIN purchases p ON p.supplier_id = s.id AND p.business_id = s.business_id
            WHERE s.business_id = %s
              AND (s.name LIKE %s OR s.phone LIKE %s OR s.material_types LIKE %s)
            GROUP BY s.id
            ORDER BY s.name ASC
            """,
            (biz_id, search, search, search),
        )
        return jsonify(suppliers)
    except DatabaseError as exc:
        return handle_db_error(exc)


@purchases_bp.post("/suppliers")
@login_required
def create_supplier():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Supplier name is required"}), 400

    biz_id = current_business_id()
    try:
        supplier_id = execute(
            """
            INSERT INTO suppliers (business_id, name, phone, email, address, material_types, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                biz_id,
                name,
                (data.get("phone") or "").strip() or None,
                (data.get("email") or "").strip() or None,
                (data.get("address") or "").strip() or None,
                (data.get("material_types") or "").strip() or None,
                (data.get("status") or "active").strip().lower(),
            ),
        )
        return jsonify({"message": "Supplier added successfully", "id": supplier_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@purchases_bp.put("/suppliers/<int:supplier_id>")
@login_required
def update_supplier(supplier_id):
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Supplier name is required"}), 400

    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM suppliers WHERE id = %s AND business_id = %s", (supplier_id, biz_id))
        if not existing:
            return jsonify({"error": "Supplier not found"}), 404

        execute(
            """
            UPDATE suppliers
            SET name = %s, phone = %s, email = %s, address = %s, material_types = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                name,
                (data.get("phone") or "").strip() or None,
                (data.get("email") or "").strip() or None,
                (data.get("address") or "").strip() or None,
                (data.get("material_types") or "").strip() or None,
                (data.get("status") or "active").strip().lower(),
                supplier_id,
                biz_id,
            ),
        )
        return jsonify({"message": "Supplier updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)


# ----------------------------------------------------
# PURCHASES / PROCUREMENT MANAGEMENT
# ----------------------------------------------------
@purchases_bp.get("")
@login_required
def list_purchases():
    search = f"%{request.args.get('search', '').strip()}%"
    biz_id = current_business_id()
    try:
        purchases = fetch_all(
            """
            SELECT p.*, rm.name AS raw_material_name, rm.unit AS raw_material_unit, rm.category AS raw_material_category,
                   s.name AS supplier_name
            FROM purchases p
            JOIN raw_materials rm ON rm.id = p.raw_material_id AND rm.business_id = p.business_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id AND s.business_id = p.business_id
            WHERE p.business_id = %s
              AND (rm.name LIKE %s OR s.name LIKE %s OR rm.category LIKE %s)
            ORDER BY p.purchase_date DESC, p.id DESC
            """,
            (biz_id, search, search, search),
        )
        return jsonify(purchases)
    except DatabaseError as exc:
        return handle_db_error(exc)


@purchases_bp.post("")
@login_required
def create_purchase():
    data = request.get_json() or {}
    biz_id = current_business_id()

    raw_mat_id = data.get("raw_material_id")
    if not raw_mat_id:
        return jsonify({"error": "Raw material selection is required"}), 400

    material = fetch_one(
        "SELECT id, name, current_stock FROM raw_materials WHERE id = %s AND business_id = %s",
        (raw_mat_id, biz_id),
    )
    if not material:
        return jsonify({"error": "Selected raw material does not exist"}), 400

    try:
        quantity = float(data.get("quantity", 0))
        if quantity <= 0:
            return jsonify({"error": "Purchase quantity must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid purchase quantity format"}), 400

    try:
        unit_price = float(data.get("unit_price", 0))
        if unit_price < 0:
            return jsonify({"error": "Unit price cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid unit price format"}), 400

    total_amount = quantity * unit_price
    supplier_id = data.get("supplier_id") or None
    status = (data.get("status") or "Received").strip()

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO purchases (business_id, supplier_id, raw_material_id, quantity, unit_price, total_amount, purchase_date, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """),
                (
                    biz_id,
                    supplier_id,
                    raw_mat_id,
                    quantity,
                    unit_price,
                    total_amount,
                    data.get("purchase_date") or None,
                    status,
                    (data.get("notes") or "").strip() or None,
                ),
            )
            purchase_id = cursor.lastrowid

            # Automatically update raw material inventory if Received
            if status.lower() == "received":
                cursor.execute(
                    normalize_query("""
                    UPDATE raw_materials
                    SET current_stock = current_stock + %s, purchase_price = %s, last_purchase_date = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND business_id = %s
                    """),
                    (quantity, unit_price, raw_mat_id, biz_id),
                )

        return jsonify({
            "message": f"Purchase recorded! {quantity} unit(s) added to '{material['name']}' stock.",
            "id": purchase_id,
            "total_amount": total_amount,
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)
