from flask import Blueprint, jsonify, request

from services.db import execute, fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

products_bp = Blueprint("products", __name__)


def validate_product_data(data):
    name = (data.get("name") or "").strip()
    if not name:
        return "Product name is required"
    sku = (data.get("sku") or "").strip()
    if not sku:
        return "SKU / Product Code is required"
    try:
        selling_price = float(data.get("selling_price", 0))
        if selling_price < 0:
            return "Selling price cannot be negative"
    except (ValueError, TypeError):
        return "Invalid selling price format"

    try:
        cost_price = float(data.get("cost_price", 0))
        if cost_price < 0:
            return "Cost price cannot be negative"
    except (ValueError, TypeError):
        return "Invalid cost price format"

    try:
        quantity = int(data.get("quantity", 0))
        if quantity < 0:
            return "Stock quantity cannot be negative"
    except (ValueError, TypeError):
        return "Invalid stock quantity format"

    try:
        min_stock = int(data.get("minimum_stock_level", 0))
        if min_stock < 0:
            return "Minimum stock level cannot be negative"
    except (ValueError, TypeError):
        return "Invalid minimum stock level format"

    return None


def is_sku_taken(sku, business_id, exclude_product_id=None):
    if exclude_product_id:
        row = fetch_one(
            "SELECT id FROM products WHERE business_id = %s AND UPPER(sku) = UPPER(%s) AND id != %s",
            (business_id, sku.strip(), exclude_product_id),
        )
    else:
        row = fetch_one(
            "SELECT id FROM products WHERE business_id = %s AND UPPER(sku) = UPPER(%s)",
            (business_id, sku.strip()),
        )
    return row is not None


@products_bp.get("")
@login_required
def list_products():
    search = f"%{request.args.get('search', '').strip()}%"
    filter_type = request.args.get("filter", "all").strip().lower()
    biz_id = current_business_id()

    query = """
        SELECT p.*, i.quantity, i.minimum_stock_level,
               CASE
                   WHEN i.quantity <= 0 THEN 'Out of Stock'
                   WHEN i.quantity <= i.minimum_stock_level THEN 'Low Stock'
                   ELSE 'In Stock'
               END AS stock_status,
               CASE WHEN i.quantity <= i.minimum_stock_level THEN 1 ELSE 0 END AS is_low_stock
        FROM products p
        LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
        WHERE p.business_id = %s
          AND (p.name LIKE %s OR p.sku LIKE %s OR p.category LIKE %s)
    """
    params = [biz_id, search, search, search]

    if filter_type == "in_stock":
        query += " AND i.quantity > i.minimum_stock_level"
    elif filter_type == "low_stock":
        query += " AND i.quantity <= i.minimum_stock_level AND i.quantity > 0"
    elif filter_type == "out_of_stock":
        query += " AND i.quantity <= 0"

    query += " ORDER BY p.created_at DESC"

    try:
        products = fetch_all(query, tuple(params))
        return jsonify(products)
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.get("/stats")
@login_required
def inventory_stats():
    biz_id = current_business_id()
    try:
        stats = fetch_one(
            """
            SELECT
                COUNT(p.id) AS total_products,
                COALESCE(SUM(i.quantity), 0) AS total_stock_units,
                COALESCE(SUM(CASE WHEN i.quantity <= i.minimum_stock_level AND i.quantity > 0 THEN 1 ELSE 0 END), 0) AS low_stock_products,
                COALESCE(SUM(CASE WHEN i.quantity <= 0 THEN 1 ELSE 0 END), 0) AS out_of_stock_products,
                COALESCE(SUM(i.quantity * p.cost_price), 0) AS total_inventory_value
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
            WHERE p.business_id = %s
            """,
            (biz_id,),
        )
        return jsonify(stats or {
            "total_products": 0,
            "total_stock_units": 0,
            "low_stock_products": 0,
            "out_of_stock_products": 0,
            "total_inventory_value": 0,
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.get("/low-stock")
@login_required
def low_stock():
    biz_id = current_business_id()
    try:
        products = fetch_all(
            """
            SELECT p.id, p.name, p.sku, p.category, i.quantity, i.minimum_stock_level,
                   CASE
                       WHEN i.quantity <= 0 THEN 'Out of Stock'
                       ELSE 'Low Stock'
                   END AS stock_status
            FROM products p
            JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
            WHERE p.business_id = %s AND i.quantity <= i.minimum_stock_level
            ORDER BY i.quantity ASC, p.name ASC
            """,
            (biz_id,),
        )
        return jsonify(products)
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.post("")
@login_required
def create_product():
    data = request.get_json() or {}
    error = validate_product_data(data)
    if error:
        return jsonify({"error": error}), 400

    biz_id = current_business_id()
    sku = data["sku"].strip()
    if is_sku_taken(sku, biz_id):
        return jsonify({"error": f"SKU '{sku}' is already assigned to another product in your catalog."}), 400

    try:
        status_val = (data.get("status") or "active").strip().lower()
        product_id = execute(
            """
            INSERT INTO products (business_id, name, sku, category, selling_price, cost_price, description, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                biz_id,
                data["name"].strip(),
                sku,
                data.get("category", "").strip() or None,
                float(data.get("selling_price", 0)),
                float(data.get("cost_price", 0)),
                data.get("description", "").strip() or None,
                status_val,
            ),
        )
        execute(
            "INSERT INTO inventory (business_id, product_id, quantity, minimum_stock_level, status) VALUES (%s, %s, %s, %s, %s)",
            (biz_id, product_id, int(data.get("quantity", 0)), int(data.get("minimum_stock_level", 0)), status_val),
        )
        return jsonify({"message": "Product created", "id": product_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.get("/<int:product_id>")
@login_required
def get_product(product_id):
    biz_id = current_business_id()
    try:
        product = fetch_one(
            """
            SELECT p.*, i.quantity, i.minimum_stock_level,
                   CASE
                       WHEN i.quantity <= 0 THEN 'Out of Stock'
                       WHEN i.quantity <= i.minimum_stock_level THEN 'Low Stock'
                       ELSE 'In Stock'
                   END AS stock_status
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
            WHERE p.id = %s AND p.business_id = %s
            """,
            (product_id, biz_id),
        )
        if not product:
            return jsonify({"error": "Product not found"}), 404
        return jsonify(product)
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.put("/<int:product_id>")
@login_required
def update_product(product_id):
    data = request.get_json() or {}
    error = validate_product_data(data)
    if error:
        return jsonify({"error": error}), 400

    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM products WHERE id = %s AND business_id = %s", (product_id, biz_id))
        if not existing:
            return jsonify({"error": "Product not found"}), 404

        sku = data["sku"].strip()
        if is_sku_taken(sku, biz_id, exclude_product_id=product_id):
            return jsonify({"error": f"SKU '{sku}' is already assigned to another product in your catalog."}), 400

        status_val = (data.get("status") or "active").strip().lower()

        execute(
            """
            UPDATE products
            SET name = %s, sku = %s, category = %s, selling_price = %s, cost_price = %s, description = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                data["name"].strip(),
                sku,
                data.get("category", "").strip() or None,
                float(data.get("selling_price", 0)),
                float(data.get("cost_price", 0)),
                data.get("description", "").strip() or None,
                status_val,
                product_id,
                biz_id,
            ),
        )
        execute(
            "UPDATE inventory SET quantity = %s, minimum_stock_level = %s, status = %s, updated_at = CURRENT_TIMESTAMP WHERE product_id = %s AND business_id = %s",
            (int(data.get("quantity", 0)), int(data.get("minimum_stock_level", 0)), status_val, product_id, biz_id),
        )
        return jsonify({"message": "Product updated"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.post("/<int:product_id>/stock-in")
@login_required
def stock_in(product_id):
    data = request.get_json() or {}
    biz_id = current_business_id()
    try:
        product = fetch_one("SELECT id, name FROM products WHERE id = %s AND business_id = %s", (product_id, biz_id))
        if not product:
            return jsonify({"error": "Product not found"}), 404

        try:
            add_qty = int(data.get("quantity", 0))
            if add_qty <= 0:
                return jsonify({"error": "Stock addition quantity must be greater than zero"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid stock addition quantity"}), 400

        execute(
            "UPDATE inventory SET quantity = quantity + %s, updated_at = CURRENT_TIMESTAMP WHERE product_id = %s AND business_id = %s",
            (add_qty, product_id, biz_id),
        )
        updated_inv = fetch_one("SELECT quantity FROM inventory WHERE product_id = %s AND business_id = %s", (product_id, biz_id))
        return jsonify({
            "message": f"Added {add_qty} unit(s) to stock for '{product['name']}'.",
            "new_quantity": updated_inv["quantity"],
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


@products_bp.delete("/<int:product_id>")
@login_required
def delete_product(product_id):
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM products WHERE id = %s AND business_id = %s", (product_id, biz_id))
        if not existing:
            return jsonify({"error": "Product not found"}), 404

        sales_count = fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE si.product_id = %s AND s.business_id = %s
            """,
            (product_id, biz_id),
        )["count"]

        if sales_count > 0:
            return jsonify({
                "error": f"Cannot delete product. This product is referenced in {sales_count} past invoice/sale record(s). Accounting and billing history must be preserved."
            }), 400

        execute("DELETE FROM products WHERE id = %s AND business_id = %s", (product_id, biz_id))
        return jsonify({"message": "Product deleted"})
    except DatabaseError as exc:
        return handle_db_error(exc)

