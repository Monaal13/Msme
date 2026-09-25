from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

from services.db import db_cursor, execute, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, current_business_id, handle_db_error, login_required

orders_bp = Blueprint("orders", __name__)


# ----------------------------------------------------
# ORDER MANAGEMENT & BOM MATERIAL REQUIREMENT CHECK
# ----------------------------------------------------
@orders_bp.get("")
@login_required
def list_orders():
    search = f"%{request.args.get('search', '').strip()}%"
    status_filter = request.args.get("status", "").strip()
    biz_id = current_business_id()

    try:
        query = """
            SELECT po.*, c.name AS customer_name, c.company_name AS customer_company, c.phone AS customer_phone,
                   e.name AS assigned_employee_name, p.name AS product_catalog_name
            FROM production_orders po
            JOIN customers c ON c.id = po.customer_id AND c.business_id = po.business_id
            LEFT JOIN employees e ON e.id = po.assigned_employee_id AND e.business_id = po.business_id
            LEFT JOIN products p ON p.id = po.product_id AND p.business_id = po.business_id
            WHERE po.business_id = %s
              AND (po.order_number LIKE %s OR po.garment_name LIKE %s OR c.name LIKE %s OR po.current_stage LIKE %s)
        """
        params = [biz_id, search, search, search, search]

        if status_filter and status_filter.lower() != "all":
            st_lower = status_filter.lower()
            if st_lower == "pending":
                query += " AND LOWER(po.status) NOT IN ('completed', 'dispatched', 'cancelled') AND LOWER(po.current_stage) NOT IN ('completed', 'dispatched', 'cancelled')"
            elif st_lower in ("in production", "in_production"):
                query += " AND (LOWER(po.status) = 'in production' OR LOWER(po.current_stage) IN ('cutting', 'stitching', 'finishing', 'in production'))"
            elif st_lower == "completed":
                query += " AND (LOWER(po.status) = 'completed' OR LOWER(po.current_stage) = 'completed')"
            elif st_lower == "dispatched":
                query += " AND (LOWER(po.status) = 'dispatched' OR LOWER(po.current_stage) = 'dispatched')"
            else:
                query += " AND (LOWER(po.status) = %s OR LOWER(po.current_stage) = %s)"
                params.extend([st_lower, st_lower])

        query += " ORDER BY po.created_at DESC, po.id DESC"
        orders = fetch_all(query, tuple(params))
        return jsonify(orders)
    except DatabaseError as exc:
        return handle_db_error(exc)


@orders_bp.get("/stats")
@login_required
def get_orders_stats():
    biz_id = current_business_id()
    try:
        total = fetch_one(
            "SELECT COUNT(*) AS val FROM production_orders WHERE business_id = %s AND LOWER(status) != 'cancelled'",
            (biz_id,),
        )["val"]

        pending = fetch_one(
            """
            SELECT COUNT(*) AS val FROM production_orders
            WHERE business_id = %s
              AND LOWER(status) NOT IN ('completed', 'dispatched', 'cancelled')
              AND LOWER(current_stage) NOT IN ('completed', 'dispatched', 'cancelled')
            """,
            (biz_id,),
        )["val"]

        in_production = fetch_one(
            """
            SELECT COUNT(*) AS val FROM production_orders
            WHERE business_id = %s
              AND LOWER(status) != 'cancelled'
              AND (LOWER(status) = 'in production' OR LOWER(current_stage) IN ('cutting', 'stitching', 'finishing', 'in production'))
            """,
            (biz_id,),
        )["val"]

        completed = fetch_one(
            """
            SELECT COUNT(*) AS val FROM production_orders
            WHERE business_id = %s
              AND (LOWER(status) = 'completed' OR LOWER(current_stage) = 'completed')
            """,
            (biz_id,),
        )["val"]

        dispatched = fetch_one(
            """
            SELECT COUNT(*) AS val FROM production_orders
            WHERE business_id = %s
              AND (LOWER(status) = 'dispatched' OR LOWER(current_stage) = 'dispatched')
            """,
            (biz_id,),
        )["val"]

        return jsonify({
            "total": total,
            "pending": pending,
            "in_production": in_production,
            "completed": completed,
            "dispatched": dispatched,
        })
    except DatabaseError as exc:
        return handle_db_error(exc)



@orders_bp.get("/board")
@login_required
def production_board():
    biz_id = current_business_id()
    try:
        orders = fetch_all(
            """
            SELECT po.*, c.name AS customer_name, e.name AS assigned_employee_name
            FROM production_orders po
            JOIN customers c ON c.id = po.customer_id AND c.business_id = po.business_id
            LEFT JOIN employees e ON e.id = po.assigned_employee_id AND e.business_id = po.business_id
            WHERE po.business_id = %s AND LOWER(po.status) != 'cancelled'
            ORDER BY po.updated_at DESC
            """,
            (biz_id,),
        )

        board = {
            "New": [],
            "Cutting": [],
            "Stitching": [],
            "Finishing": [],
            "Quality Check": [],
            "Packing": [],
            "Ready for Dispatch": [],
            "Completed": [],
        }

        for ord_item in orders:
            stage = ord_item.get("current_stage") or "New"
            if stage in board:
                board[stage].append(ord_item)
            else:
                board["New"].append(ord_item)

        return jsonify(board)
    except DatabaseError as exc:
        return handle_db_error(exc)


@orders_bp.post("")
@login_required
def create_order():
    data = request.get_json() or {}
    biz_id = current_business_id()

    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Customer selection is required"}), 400

    customer = fetch_one("SELECT id, name FROM customers WHERE id = %s AND business_id = %s", (customer_id, biz_id))
    if not customer:
        return jsonify({"error": "Selected customer does not exist"}), 400

    garment_name = (data.get("garment_name") or "").strip()
    if not garment_name:
        return jsonify({"error": "Garment / Product name is required"}), 400

    try:
        quantity = int(data.get("quantity", 1))
        if quantity <= 0:
            return jsonify({"error": "Order quantity must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid order quantity"}), 400

    try:
        price = float(data.get("price", 0))
        if price < 0:
            return jsonify({"error": "Price cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid price format"}), 400

    expected_delivery = data.get("expected_delivery_date") or (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    # Raw material requirements (BOM) input from frontend user
    raw_material_reqs = data.get("materials") or []

    try:
        with db_cursor(commit=True) as cursor:
            # Generate unique order number
            cursor.execute(normalize_query("SELECT MAX(id) AS max_id FROM production_orders WHERE business_id = %s"), (biz_id,))
            max_row = cursor.fetchone()
            next_num = (max_row["max_id"] or 0) + 1 if max_row else 1
            order_number = f"ORD-{next_num:04d}"

            cursor.execute(
                normalize_query("""
                INSERT INTO production_orders (
                    business_id, customer_id, product_id, order_number, garment_name, design, size, color,
                    quantity, price, current_stage, assigned_employee_id, start_date, expected_completion, special_requirements, notes, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'New', %s, %s, %s, %s, %s, 'New')
                """),
                (
                    biz_id,
                    customer_id,
                    data.get("product_id") or None,
                    order_number,
                    garment_name,
                    (data.get("design") or "").strip() or None,
                    (data.get("size") or "").strip() or None,
                    (data.get("color") or "").strip() or None,
                    quantity,
                    price,
                    data.get("assigned_employee_id") or None,
                    datetime.now().strftime("%Y-%m-%d"),
                    expected_delivery,
                    (data.get("special_requirements") or "").strip() or None,
                    (data.get("notes") or "").strip() or None,
                ),
            )
            order_id = cursor.lastrowid

            # Evaluate Raw Material BOM Requirements
            shortage_count = 0
            materials_evaluated = []

            for req in raw_material_reqs:
                mat_id = req.get("raw_material_id")
                req_qty = float(req.get("required_quantity", 0))
                if mat_id and req_qty > 0:
                    cursor.execute(
                        normalize_query("SELECT id, name, current_stock, unit FROM raw_materials WHERE id = %s AND business_id = %s"),
                        (mat_id, biz_id),
                    )
                    mat = cursor.fetchone()
                    if mat:
                        avail = mat["current_stock"]
                        status = "Available" if avail >= req_qty else "Shortage"
                        if status == "Shortage":
                            shortage_count += 1
                        
                        cursor.execute(
                            normalize_query("""
                            INSERT INTO order_material_requirements (production_order_id, raw_material_id, required_quantity, allocated_quantity, status)
                            VALUES (%s, %s, %s, %s, %s)
                            """),
                            (order_id, mat_id, req_qty, min(avail, req_qty), status),
                        )
                        materials_evaluated.append({
                            "material_id": mat_id,
                            "name": mat["name"],
                            "required": req_qty,
                            "available": avail,
                            "shortage": max(0, req_qty - avail),
                            "status": status,
                            "unit": mat["unit"],
                        })

            # Set initial order status based on raw material availability
            initial_status = "Material Pending" if shortage_count > 0 else "Material Ready"
            cursor.execute(
                normalize_query("UPDATE production_orders SET status = %s WHERE id = %s"),
                (initial_status, order_id),
            )

        return jsonify({
            "message": f"Order {order_number} created successfully",
            "id": order_id,
            "order_number": order_number,
            "status": initial_status,
            "has_shortage": shortage_count > 0,
            "materials_evaluated": materials_evaluated,
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@orders_bp.get("/<int:order_id>")
@login_required
def get_order(order_id):
    biz_id = current_business_id()
    try:
        order = fetch_one(
            """
            SELECT po.*, c.name AS customer_name, c.company_name AS customer_company, c.phone AS customer_phone, c.email AS customer_email,
                   e.name AS assigned_employee_name, p.name AS product_catalog_name
            FROM production_orders po
            JOIN customers c ON c.id = po.customer_id AND c.business_id = po.business_id
            LEFT JOIN employees e ON e.id = po.assigned_employee_id AND e.business_id = po.business_id
            LEFT JOIN products p ON p.id = po.product_id AND p.business_id = po.business_id
            WHERE po.id = %s AND po.business_id = %s
            """,
            (order_id, biz_id),
        )
        if not order:
            return jsonify({"error": "Production order not found"}), 404

        # Fetch Raw Material requirements vs availability
        materials = fetch_all(
            """
            SELECT omr.*, rm.name AS material_name, rm.current_stock AS available_stock, rm.unit AS unit, rm.purchase_price,
                   (omr.required_quantity - rm.current_stock) AS shortage_quantity
            FROM order_material_requirements omr
            JOIN raw_materials rm ON rm.id = omr.raw_material_id AND rm.business_id = %s
            WHERE omr.production_order_id = %s
            """,
            (biz_id, order_id),
        )
        order["material_requirements"] = materials

        # Fetch Quality check records
        q_checks = fetch_all(
            """
            SELECT qc.*, e.name AS inspector_name
            FROM quality_checks qc
            LEFT JOIN employees e ON e.id = qc.checked_by_employee_id
            WHERE qc.production_order_id = %s
            ORDER BY qc.created_at DESC
            """,
            (order_id,),
        )
        order["quality_checks"] = q_checks

        # Fetch Packing records
        packing = fetch_all(
            """
            SELECT pr.*, e.name AS packer_name
            FROM packing_records pr
            LEFT JOIN employees e ON e.id = pr.packed_by_employee_id
            WHERE pr.production_order_id = %s
            ORDER BY pr.created_at DESC
            """,
            (order_id,),
        )
        order["packing_records"] = packing

        return jsonify(order)
    except DatabaseError as exc:
        return handle_db_error(exc)


@orders_bp.put("/<int:order_id>/stage")
@login_required
def update_stage(order_id):
    data = request.get_json() or {}
    new_stage = (data.get("stage") or "").strip()
    valid_stages = ["New", "Cutting", "Stitching", "Finishing", "Quality Check", "Packing", "Ready for Dispatch", "Completed"]

    if new_stage not in valid_stages:
        return jsonify({"error": f"Invalid stage. Allowed stages: {', '.join(valid_stages)}"}), 400

    biz_id = current_business_id()
    try:
        order = fetch_one("SELECT id, order_number, quantity, product_id, garment_name FROM production_orders WHERE id = %s AND business_id = %s", (order_id, biz_id))
        if not order:
            return jsonify({"error": "Order not found"}), 404

        status_val = "In Production" if new_stage in ["Cutting", "Stitching", "Finishing"] else new_stage
        actual_comp = datetime.now().strftime("%Y-%m-%d") if new_stage == "Completed" else None

        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                UPDATE production_orders
                SET current_stage = %s, status = %s, actual_completion = COALESCE(%s, actual_completion), updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND business_id = %s
                """),
                (new_stage, status_val, actual_comp, order_id, biz_id),
            )

            # If order moves to Ready for Dispatch / Completed, update finished goods catalog stock!
            if new_stage in ["Ready for Dispatch", "Completed"] and order["product_id"]:
                cursor.execute(
                    normalize_query("UPDATE inventory SET quantity = quantity + %s WHERE product_id = %s AND business_id = %s"),
                    (order["quantity"], order["product_id"], biz_id),
                )

        return jsonify({
            "message": f"Order {order['order_number']} stage updated to '{new_stage}'",
            "current_stage": new_stage,
            "status": status_val,
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


# ----------------------------------------------------
# QUALITY CONTROL AUDIT
# ----------------------------------------------------
@orders_bp.post("/<int:order_id>/quality-check")
@login_required
def submit_quality_check(order_id):
    data = request.get_json() or {}
    biz_id = current_business_id()

    order = fetch_one("SELECT id, order_number, quantity FROM production_orders WHERE id = %s AND business_id = %s", (order_id, biz_id))
    if not order:
        return jsonify({"error": "Order not found"}), 404

    try:
        checked_qty = int(data.get("checked_quantity", order["quantity"]))
        passed_qty = int(data.get("passed_quantity", 0))
        failed_qty = int(data.get("failed_quantity", 0))
        defective_qty = int(data.get("defective_quantity", 0))
        if checked_qty <= 0 or passed_qty < 0 or failed_qty < 0:
            return jsonify({"error": "Invalid quantity counts for quality check"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numbers in quality check data"}), 400

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO quality_checks (production_order_id, checked_quantity, passed_quantity, failed_quantity, defective_quantity, remarks, checked_by_employee_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """),
                (
                    order_id,
                    checked_qty,
                    passed_qty,
                    failed_qty,
                    defective_qty,
                    (data.get("remarks") or "").strip() or None,
                    data.get("checked_by_employee_id") or None,
                ),
            )

            # Move order stage to Quality Check / Packing based on result
            next_stage = "Packing" if passed_qty > 0 else "Quality Check"
            cursor.execute(
                normalize_query("UPDATE production_orders SET current_stage = %s, status = 'Quality Check', updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s"),
                (next_stage, order_id, biz_id),
            )

        return jsonify({
            "message": f"Quality check logged for Order {order['order_number']}. Passed: {passed_qty}, Rejected: {failed_qty}",
            "next_stage": next_stage,
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


# ----------------------------------------------------
# PACKING RECORD
# ----------------------------------------------------
@orders_bp.post("/<int:order_id>/packing")
@login_required
def submit_packing(order_id):
    data = request.get_json() or {}
    biz_id = current_business_id()

    order = fetch_one("SELECT id, order_number, quantity FROM production_orders WHERE id = %s AND business_id = %s", (order_id, biz_id))
    if not order:
        return jsonify({"error": "Order not found"}), 404

    try:
        packed_qty = int(data.get("packed_quantity", order["quantity"]))
        if packed_qty <= 0:
            return jsonify({"error": "Packed quantity must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid packed quantity"}), 400

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO packing_records (production_order_id, packed_quantity, packaging_material_used, packed_by_employee_id)
                VALUES (%s, %s, %s, %s)
                """),
                (
                    order_id,
                    packed_qty,
                    (data.get("packaging_material_used") or "").strip() or None,
                    data.get("packed_by_employee_id") or None,
                ),
            )

            cursor.execute(
                normalize_query("UPDATE production_orders SET current_stage = 'Ready for Dispatch', status = 'Packed', updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s"),
                (order_id, biz_id),
            )

        return jsonify({
            "message": f"Order {order['order_number']} packed successfully and is Ready for Dispatch!",
            "current_stage": "Ready for Dispatch",
            "status": "Packed",
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)
