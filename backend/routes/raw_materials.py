from flask import Blueprint, jsonify, request

from services.db import execute, fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

raw_materials_bp = Blueprint("raw_materials", __name__)


def validate_raw_material(data):
    name = (data.get("name") or "").strip()
    if not name:
        return "Material name is required"
    category = (data.get("category") or "").strip()
    if not category:
        return "Category is required (Fabric, Thread, Buttons, Zippers, Labels, Packaging Material)"
    try:
        current_stock = float(data.get("current_stock", 0))
        if current_stock < 0:
            return "Current stock cannot be negative"
    except (ValueError, TypeError):
        return "Invalid current stock format"

    try:
        minimum_stock = float(data.get("minimum_stock", 0))
        if minimum_stock < 0:
            return "Minimum stock cannot be negative"
    except (ValueError, TypeError):
        return "Invalid minimum stock format"

    try:
        purchase_price = float(data.get("purchase_price", 0))
        if purchase_price < 0:
            return "Purchase price cannot be negative"
    except (ValueError, TypeError):
        return "Invalid purchase price format"

    return None


@raw_materials_bp.get("")
@login_required
def list_raw_materials():
    search = f"%{request.args.get('search', '').strip()}%"
    category = request.args.get("category", "").strip()
    filter_type = request.args.get("filter", "all").strip().lower()
    biz_id = current_business_id()

    try:
        query = """
            SELECT rm.*, s.name AS supplier_name,
                   CASE
                       WHEN rm.current_stock <= 0 THEN 'Out of Stock'
                       WHEN rm.current_stock <= rm.minimum_stock THEN 'Low Stock'
                       ELSE 'In Stock'
                   END AS stock_status,
                   CASE WHEN rm.current_stock <= rm.minimum_stock THEN 1 ELSE 0 END AS is_low_stock
            FROM raw_materials rm
            LEFT JOIN suppliers s ON s.id = rm.supplier_id AND s.business_id = rm.business_id
            WHERE rm.business_id = %s
              AND (rm.name LIKE %s OR rm.category LIKE %s OR rm.unit LIKE %s)
        """
        params = [biz_id, search, search, search]

        if category and category.lower() != "all":
            query += " AND LOWER(rm.category) = %s"
            params.append(category.lower())

        if filter_type == "low_stock":
            query += " AND rm.current_stock <= rm.minimum_stock"
        elif filter_type == "out_of_stock":
            query += " AND rm.current_stock <= 0"

        query += " ORDER BY rm.created_at DESC"

        materials = fetch_all(query, tuple(params))
        return jsonify(materials)
    except DatabaseError as exc:
        return handle_db_error(exc)


@raw_materials_bp.get("/stats")
@login_required
def raw_material_stats():
    biz_id = current_business_id()
    try:
        stats = fetch_one(
            """
            SELECT
                COUNT(id) AS total_materials,
                COALESCE(SUM(current_stock), 0) AS total_stock_volume,
                COALESCE(SUM(CASE WHEN current_stock <= minimum_stock AND current_stock > 0 THEN 1 ELSE 0 END), 0) AS low_stock_materials,
                COALESCE(SUM(CASE WHEN current_stock <= 0 THEN 1 ELSE 0 END), 0) AS out_of_stock_materials,
                COALESCE(SUM(current_stock * purchase_price), 0) AS total_material_value
            FROM raw_materials
            WHERE business_id = %s
            """,
            (biz_id,),
        )
        return jsonify(stats or {
            "total_materials": 0,
            "total_stock_volume": 0,
            "low_stock_materials": 0,
            "out_of_stock_materials": 0,
            "total_material_value": 0,
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


@raw_materials_bp.post("")
@login_required
def create_raw_material():
    data = request.get_json() or {}
    error = validate_raw_material(data)
    if error:
        return jsonify({"error": error}), 400

    biz_id = current_business_id()
    try:
        mat_id = execute(
            """
            INSERT INTO raw_materials (business_id, name, category, unit, current_stock, minimum_stock, supplier_id, purchase_price, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                biz_id,
                data["name"].strip(),
                data["category"].strip(),
                (data.get("unit") or "meters").strip(),
                float(data.get("current_stock", 0)),
                float(data.get("minimum_stock", 0)),
                data.get("supplier_id") or None,
                float(data.get("purchase_price", 0)),
                (data.get("status") or "active").strip().lower(),
            ),
        )
        return jsonify({"message": "Raw material added successfully", "id": mat_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@raw_materials_bp.get("/<int:mat_id>")
@login_required
def get_raw_material(mat_id):
    biz_id = current_business_id()
    try:
        material = fetch_one(
            """
            SELECT rm.*, s.name AS supplier_name
            FROM raw_materials rm
            LEFT JOIN suppliers s ON s.id = rm.supplier_id AND s.business_id = rm.business_id
            WHERE rm.id = %s AND rm.business_id = %s
            """,
            (mat_id, biz_id),
        )
        if not material:
            return jsonify({"error": "Raw material not found"}), 404
        return jsonify(material)
    except DatabaseError as exc:
        return handle_db_error(exc)


@raw_materials_bp.put("/<int:mat_id>")
@login_required
def update_raw_material(mat_id):
    data = request.get_json() or {}
    error = validate_raw_material(data)
    if error:
        return jsonify({"error": error}), 400

    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM raw_materials WHERE id = %s AND business_id = %s", (mat_id, biz_id))
        if not existing:
            return jsonify({"error": "Raw material not found"}), 404

        execute(
            """
            UPDATE raw_materials
            SET name = %s, category = %s, unit = %s, current_stock = %s, minimum_stock = %s,
                supplier_id = %s, purchase_price = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                data["name"].strip(),
                data["category"].strip(),
                (data.get("unit") or "meters").strip(),
                float(data.get("current_stock", 0)),
                float(data.get("minimum_stock", 0)),
                data.get("supplier_id") or None,
                float(data.get("purchase_price", 0)),
                (data.get("status") or "active").strip().lower(),
                mat_id,
                biz_id,
            ),
        )
        return jsonify({"message": "Raw material updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@raw_materials_bp.post("/<int:mat_id>/stock-in")
@login_required
def stock_in_raw_material(mat_id):
    data = request.get_json() or {}
    biz_id = current_business_id()
    try:
        material = fetch_one("SELECT id, name FROM raw_materials WHERE id = %s AND business_id = %s", (mat_id, biz_id))
        if not material:
            return jsonify({"error": "Raw material not found"}), 404

        try:
            add_qty = float(data.get("quantity", 0))
            if add_qty <= 0:
                return jsonify({"error": "Stock addition quantity must be greater than zero"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid stock quantity format"}), 400

        execute(
            "UPDATE raw_materials SET current_stock = current_stock + %s, last_purchase_date = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s",
            (add_qty, mat_id, biz_id),
        )
        updated = fetch_one("SELECT current_stock FROM raw_materials WHERE id = %s AND business_id = %s", (mat_id, biz_id))
        return jsonify({
            "message": f"Added {add_qty} unit(s) to '{material['name']}'.",
            "new_stock": updated["current_stock"],
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


@raw_materials_bp.delete("/<int:mat_id>")
@login_required
def delete_raw_material(mat_id):
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM raw_materials WHERE id = %s AND business_id = %s", (mat_id, biz_id))
        if not existing:
            return jsonify({"error": "Raw material not found"}), 404

        purchase_count = fetch_one(
            "SELECT COUNT(*) AS count FROM purchases WHERE raw_material_id = %s AND business_id = %s",
            (mat_id, biz_id),
        )["count"]

        if purchase_count > 0:
            return jsonify({
                "error": f"Cannot delete material. It has {purchase_count} past purchase records."
            }), 400

        execute("DELETE FROM raw_materials WHERE id = %s AND business_id = %s", (mat_id, biz_id))
        return jsonify({"message": "Raw material deleted successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)
