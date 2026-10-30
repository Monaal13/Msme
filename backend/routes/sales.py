from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

from services.db import db_cursor, execute, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, current_business_id, handle_db_error, login_required

sales_bp = Blueprint("sales", __name__)


def process_sale_record(sale):
    if not sale:
        return sale
    payment_status = (sale.get("payment_status") or "unpaid").lower()
    due_date_str = sale.get("due_date")
    overdue_days = 0

    if payment_status != "paid" and due_date_str:
        try:
            due_date_obj = datetime.strptime(due_date_str[:10], "%Y-%m-%d").date()
            today = datetime.now().date()
            if today > due_date_obj:
                overdue_days = (today - due_date_obj).days
                sale["payment_status"] = "overdue"
        except ValueError:
            pass

    sale["overdue_days"] = overdue_days
    return sale


@sales_bp.get("")
@login_required
def list_sales():
    search = f"%{request.args.get('search', '').strip()}%"
    status = request.args.get("status", "").strip().lower()
    biz_id = current_business_id()
    try:
        query = """
            SELECT s.*, c.name AS customer_name, c.company_name AS customer_company
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id AND c.business_id = s.business_id
            WHERE s.business_id = %s
              AND (s.invoice_number LIKE %s OR c.name LIKE %s OR c.company_name LIKE %s OR s.payment_status LIKE %s)
        """
        params = [biz_id, search, search, search, search]

        if status in ("paid", "unpaid"):
            query += " AND LOWER(s.payment_status) = %s"
            params.append(status)

        query += " ORDER BY s.sale_date DESC, s.id DESC"
        sales = fetch_all(query, tuple(params))
        processed_sales = [process_sale_record(sale) for sale in sales]
        if status == "overdue":
            processed_sales = [s for s in processed_sales if s.get("payment_status") == "overdue"]
        return jsonify(processed_sales)
    except DatabaseError as exc:
        return handle_db_error(exc)


@sales_bp.post("")
@login_required
def create_sale():
    data = request.get_json() or {}
    biz_id = current_business_id()

    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Customer is required"}), 400

    customer = fetch_one(
        "SELECT id, name FROM customers WHERE id = %s AND business_id = %s AND LOWER(COALESCE(status, 'active')) = 'active'",
        (customer_id, biz_id),
    )
    if not customer:
        return jsonify({"error": "Selected customer does not exist or does not belong to your business"}), 400

    items = data.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "At least one product line item is required"}), 400

    due_date = data.get("due_date")
    if not due_date:
        due_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")

    pay_status = (data.get("payment_status") or "unpaid").strip().lower()
    pay_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if pay_status == "paid" else None

    try:
        subtotal_sum = 0
        prepared_items = []
        for item in items:
            prod_id = item.get("product_id")
            if not prod_id:
                return jsonify({"error": "Product selection is required for all line items"}), 400

            product = fetch_one(
                "SELECT id, name, selling_price FROM products WHERE id = %s AND business_id = %s",
                (prod_id, biz_id),
            )
            if not product:
                return jsonify({"error": f"Selected product (ID {prod_id}) is invalid or does not belong to your business"}), 400

            try:
                quantity = int(item.get("quantity", 1))
                if quantity <= 0:
                    return jsonify({"error": f"Quantity for '{product['name']}' must be greater than zero"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": f"Invalid quantity for '{product['name']}'"}), 400

            inv = fetch_one(
                "SELECT quantity FROM inventory WHERE product_id = %s AND business_id = %s",
                (product["id"], biz_id),
            )
            available_stock = inv["quantity"] if inv else 0
            if quantity > available_stock:
                return jsonify({
                    "error": f"Insufficient stock for '{product['name']}'. Available stock: {available_stock}, Requested: {quantity}"
                }), 400

            unit_price = float(item.get("unit_price") if item.get("unit_price") is not None else product["selling_price"])
            if unit_price < 0:
                return jsonify({"error": f"Unit price for '{product['name']}' cannot be negative"}), 400

            line_subtotal = quantity * unit_price
            subtotal_sum += line_subtotal
            prepared_items.append((product["id"], quantity, unit_price, line_subtotal))

        try:
            discount = float(data.get("discount", 0))
            if discount < 0:
                return jsonify({"error": "Discount amount cannot be negative"}), 400
            if discount > subtotal_sum:
                return jsonify({"error": "Discount cannot exceed invoice subtotal"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid discount format"}), 400

        grand_total = subtotal_sum - discount

        with db_cursor(commit=True) as cursor:
            cursor.execute(
                normalize_query("""
                INSERT INTO sales (business_id, customer_id, invoice_number, subtotal, total_amount, payment_status, payment_date, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """),
                (
                    biz_id,
                    customer_id,
                    data.get("invoice_number"),
                    subtotal_sum,
                    grand_total,
                    pay_status,
                    pay_date,
                    due_date,
                ),
            )
            sale_id = cursor.lastrowid
            invoice_num = data.get("invoice_number") or f"INV-{sale_id:05d}"
            if not data.get("invoice_number"):
                cursor.execute(
                    normalize_query("UPDATE sales SET invoice_number = %s WHERE id = %s"),
                    (invoice_num, sale_id),
                )

            for product_id, quantity, unit_price, line_subtotal in prepared_items:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                    """),
                    (sale_id, product_id, quantity, unit_price, line_subtotal),
                )
                cursor.execute(
                    normalize_query("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND business_id = %s"),
                    (quantity, product_id, biz_id),
                )

            action_desc = "Invoice Created & Paid" if pay_status == "paid" else "Invoice Created"
            cursor.execute(
                normalize_query("INSERT INTO payment_history (sale_id, action) VALUES (%s, %s)"),
                (sale_id, action_desc),
            )

        try:
            from services.notifications import create_purchase_notifications
            create_purchase_notifications(biz_id, sale_id)
        except Exception as e:
            # Prevent failures in messaging from crashing the sale API response
            pass

        return jsonify({
            "message": "Invoice created successfully",
            "id": sale_id,
            "invoice_number": invoice_num,
            "total_amount": grand_total,
            "payment_status": pay_status,
            "payment_date": pay_date,
            "due_date": due_date,
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@sales_bp.get("/<int:sale_id>")
@login_required
def get_sale(sale_id):
    biz_id = current_business_id()
    try:
        sale = fetch_one(
            """
            SELECT s.*,
                   c.name AS customer_name, c.company_name AS customer_company,
                   c.phone AS customer_phone, c.email AS customer_email, c.address AS customer_address,
                   b.name AS business_name, b.phone AS business_phone, b.email AS business_email, b.address AS business_address
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id AND c.business_id = s.business_id
            LEFT JOIN businesses b ON b.id = s.business_id
            WHERE s.id = %s AND s.business_id = %s
            """,
            (sale_id, biz_id),
        )
        if not sale:
            return jsonify({"error": "Invoice not found"}), 404

        sale = process_sale_record(sale)

        items = fetch_all(
            """
            SELECT si.*, p.name AS product_name, p.sku
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = %s
            """,
            (sale_id,),
        )
        sale["items"] = items

        history = fetch_all(
            "SELECT id, action, created_at FROM payment_history WHERE sale_id = %s ORDER BY id ASC",
            (sale_id,),
        )
        sale["payment_history"] = history

        return jsonify(sale)
    except DatabaseError as exc:
        return handle_db_error(exc)


@sales_bp.put("/<int:sale_id>")
@login_required
def update_sale_status(sale_id):
    data = request.get_json() or {}
    biz_id = current_business_id()
    try:
        sale = fetch_one("SELECT * FROM sales WHERE id = %s AND business_id = %s", (sale_id, biz_id))
        if not sale:
            return jsonify({"error": "Invoice not found"}), 404

        new_status = data.get("payment_status")
        new_due_date = data.get("due_date")

        current_status = (sale.get("payment_status") or "unpaid").lower()
        payment_date = sale.get("payment_date")

        if new_status:
            new_status = new_status.strip().lower()
            if new_status == "paid" and current_status != "paid":
                payment_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                execute(
                    "UPDATE sales SET payment_status = 'paid', payment_date = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s",
                    (payment_date, sale_id, biz_id),
                )
                execute(
                    "INSERT INTO payment_history (sale_id, action) VALUES (%s, %s)",
                    (sale_id, "Payment Received"),
                )
            elif new_status == "unpaid" and current_status == "paid":
                payment_date = None
                execute(
                    "UPDATE sales SET payment_status = 'unpaid', payment_date = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s",
                    (sale_id, biz_id),
                )
                execute(
                    "INSERT INTO payment_history (sale_id, action) VALUES (%s, %s)",
                    (sale_id, "Status changed to Unpaid"),
                )

        if new_due_date:
            execute(
                "UPDATE sales SET due_date = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s",
                (new_due_date, sale_id, biz_id),
            )

        updated_sale = fetch_one("SELECT * FROM sales WHERE id = %s AND business_id = %s", (sale_id, biz_id))
        return jsonify({
            "message": "Payment recorded successfully" if new_status == "paid" else "Invoice updated successfully",
            "sale": process_sale_record(updated_sale),
        })
    except DatabaseError as exc:
        return handle_db_error(exc)


@sales_bp.delete("/<int:sale_id>")
@login_required
def delete_sale(sale_id):
    biz_id = current_business_id()
    try:
        sale = fetch_one("SELECT id FROM sales WHERE id = %s AND business_id = %s", (sale_id, biz_id))
        if not sale:
            return jsonify({"error": "Invoice not found"}), 404

        return jsonify({
            "error": "Cannot delete issued invoices. Deleting transactions breaks accounting integrity and transaction history."
        }), 400
    except DatabaseError as exc:
        return handle_db_error(exc)


