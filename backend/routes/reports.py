from flask import Blueprint, jsonify, request

from services.db import fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

reports_bp = Blueprint("reports", __name__)


def get_date_where_clause(date_col, date_range, start_date=None, end_date=None, created_col="created_at"):
    if date_range == "this_month":
        return f" AND strftime('%Y-%m', COALESCE({date_col}, {created_col})) = strftime('%Y-%m', 'now')", []
    elif date_range == "last_month":
        return f" AND strftime('%Y-%m', COALESCE({date_col}, {created_col})) = strftime('%Y-%m', 'now', '-1 month')", []
    elif date_range == "custom" and start_date and end_date:
        return f" AND DATE(COALESCE({date_col}, {created_col})) >= DATE(%s) AND DATE(COALESCE({date_col}, {created_col})) <= DATE(%s)", [start_date, end_date]
    return "", []


@reports_bp.get("/summary")
@reports_bp.get("/business-summary")
@login_required
def report_summary():
    biz_id = current_business_id()
    date_range = request.args.get("date_range", "all").strip().lower()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    try:
        sales_date_sql, sales_date_params = get_date_where_clause("s.sale_date", date_range, start_date, end_date, "s.created_at")
        expense_date_sql, expense_date_params = get_date_where_clause("e.expense_date", date_range, start_date, end_date, "e.created_at")
        simple_sales_date_sql, simple_sales_params = get_date_where_clause("sale_date", date_range, start_date, end_date, "created_at")
        simple_exp_date_sql, simple_exp_params = get_date_where_clause("expense_date", date_range, start_date, end_date, "created_at")

        # 1. Executive Summary & Profit
        sales_summary = fetch_one(
            f"SELECT COALESCE(SUM(total_amount), 0) AS total_sales, COUNT(id) AS invoice_count, COALESCE(AVG(total_amount), 0) AS avg_invoice FROM sales WHERE business_id = %s {simple_sales_date_sql}",
            (biz_id, *simple_sales_params),
        )
        expense_summary = fetch_one(
            f"SELECT COALESCE(SUM(amount), 0) AS total_expenses, COUNT(id) AS expense_count, COALESCE(AVG(amount), 0) AS avg_expense FROM expenses WHERE business_id = %s {simple_exp_date_sql}",
            (biz_id, *simple_exp_params),
        )

        total_sales = float(sales_summary["total_sales"] or 0)
        total_expenses = float(expense_summary["total_expenses"] or 0)
        net_profit = total_sales - total_expenses
        profit_margin = round((net_profit / total_sales * 100), 2) if total_sales > 0 else 0.0

        # 2. Sales Report Breakdown
        top_selling_products = fetch_all(
            f"""
            SELECT p.name, p.sku, COALESCE(SUM(si.quantity), 0) AS quantity_sold, COALESCE(SUM(si.subtotal), 0) AS revenue
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id AND p.business_id = s.business_id
            WHERE s.business_id = %s {sales_date_sql}
            GROUP BY p.id, p.name, p.sku
            ORDER BY quantity_sold DESC, revenue DESC
            LIMIT 10
            """,
            (biz_id, *sales_date_params),
        )
        period_invoices = fetch_all(
            f"""
            SELECT s.id, s.invoice_number, c.name AS customer_name, s.sale_date, s.total_amount, s.payment_status
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id AND c.business_id = s.business_id
            WHERE s.business_id = %s {sales_date_sql}
            ORDER BY s.sale_date DESC, s.id DESC
            LIMIT 25
            """,
            (biz_id, *sales_date_params),
        )

        # 3. Expense Report Breakdown
        top_expense_category = fetch_one(
            f"SELECT category, SUM(amount) AS cat_total FROM expenses e WHERE e.business_id = %s AND e.category IS NOT NULL AND e.category != '' {expense_date_sql} GROUP BY e.category ORDER BY cat_total DESC LIMIT 1",
            (biz_id, *expense_date_params),
        )
        expenses_by_category = fetch_all(
            f"SELECT e.category, COUNT(e.id) AS count, COALESCE(SUM(e.amount), 0) AS total_amount FROM expenses e WHERE e.business_id = %s {expense_date_sql} GROUP BY e.category ORDER BY total_amount DESC",
            (biz_id, *expense_date_params),
        )
        period_expenses = fetch_all(
            f"SELECT e.id, e.title, e.category, e.expense_date, e.amount, e.notes FROM expenses e WHERE e.business_id = %s {expense_date_sql} ORDER BY COALESCE(e.expense_date, e.created_at) DESC, e.id DESC LIMIT 25",
            (biz_id, *expense_date_params),
        )

        # 4. Customer Report Breakdown
        total_customers = fetch_one("SELECT COUNT(*) AS value FROM customers WHERE business_id = %s", (biz_id,))["value"]
        top_customers = fetch_all(
            f"""
            SELECT c.id, c.name, c.company_name, COUNT(s.id) AS total_orders, COALESCE(SUM(s.total_amount), 0) AS total_purchase, MAX(s.sale_date) AS last_purchase_date
            FROM customers c
            JOIN sales s ON s.customer_id = c.id AND s.business_id = c.business_id
            WHERE c.business_id = %s {sales_date_sql}
            GROUP BY c.id, c.name, c.company_name
            ORDER BY total_purchase DESC
            LIMIT 10
            """,
            (biz_id, *sales_date_params),
        )

        # 5. Inventory Report Breakdown
        inv_summary = fetch_one(
            """
            SELECT
                COUNT(p.id) AS total_products,
                COALESCE(SUM(i.quantity), 0) AS total_stock_units,
                COALESCE(SUM(i.quantity * p.cost_price), 0) AS total_inventory_value,
                COALESCE(SUM(CASE WHEN i.quantity <= i.minimum_stock_level AND i.quantity > 0 THEN 1 ELSE 0 END), 0) AS low_stock_count,
                COALESCE(SUM(CASE WHEN i.quantity <= 0 THEN 1 ELSE 0 END), 0) AS out_of_stock_count
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
            WHERE p.business_id = %s
            """,
            (biz_id,),
        )
        products_table = fetch_all(
            """
            SELECT p.id, p.name, p.sku, p.category, p.selling_price, p.cost_price,
                   COALESCE(i.quantity, 0) AS quantity, COALESCE(i.minimum_stock_level, 0) AS minimum_stock_level,
                   (COALESCE(i.quantity, 0) * p.cost_price) AS inventory_value,
                   CASE
                       WHEN COALESCE(i.quantity, 0) <= 0 THEN 'Out of Stock'
                       WHEN COALESCE(i.quantity, 0) <= COALESCE(i.minimum_stock_level, 0) THEN 'Low Stock'
                       ELSE 'In Stock'
                   END AS stock_status
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
            WHERE p.business_id = %s
            ORDER BY p.name ASC
            LIMIT 50
            """,
            (biz_id,),
        )

        # 6. HR Report Breakdown
        hr_summary = fetch_one(
            """
            SELECT
                COUNT(e.id) AS total_employees,
                COALESCE(SUM(CASE WHEN LOWER(e.status) = 'active' THEN 1 ELSE 0 END), 0) AS active_employees,
                COALESCE(SUM(CASE WHEN LOWER(e.status) = 'inactive' THEN 1 ELSE 0 END), 0) AS inactive_employees,
                COALESCE(SUM(e.salary), 0) AS total_payroll,
                COALESCE(AVG(e.salary), 0) AS average_salary
            FROM employees e
            WHERE e.business_id = %s
            """,
            (biz_id,),
        )
        total_depts = fetch_one("SELECT COUNT(*) AS value FROM departments WHERE business_id = %s", (biz_id,))["value"]
        departments_table = fetch_all(
            """
            SELECT d.id, d.name, d.description, COUNT(e.id) AS employee_count, COALESCE(SUM(e.salary), 0) AS dept_payroll
            FROM departments d
            LEFT JOIN employees e ON e.department_id = d.id AND e.business_id = d.business_id
            WHERE d.business_id = %s
            GROUP BY d.id, d.name, d.description
            ORDER BY d.name ASC
            """,
            (biz_id,),
        )

        biz_info = fetch_one("SELECT name, email, phone, address FROM businesses WHERE id = %s", (biz_id,)) or {}

        # 7. Communication Report Breakdown
        msg_date_sql, msg_date_params = get_date_where_clause("created_at", date_range, start_date, end_date, "created_at")
        messages_stats = fetch_one(
            f"""
            SELECT 
                COUNT(id) AS total_messages,
                COALESCE(SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END), 0) AS sent_count,
                COALESCE(SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END), 0) AS scheduled_count,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count
            FROM messages
            WHERE business_id = %s {msg_date_sql}
            """,
            (biz_id, *msg_date_params),
        )

        # 8. Customer Retention Report Breakdown
        retention_customers = fetch_all(
            """
            SELECT 
                c.id, c.name, c.phone, c.company_name, c.email,
                COUNT(s.id) AS total_orders,
                COALESCE(SUM(s.total_amount), 0) AS total_purchase,
                MAX(s.sale_date) AS last_purchase_date,
                CASE
                    WHEN COUNT(s.id) = 1 THEN 'New'
                    WHEN COUNT(s.id) > 1 THEN 'Returning'
                    ELSE 'Prospect'
                END AS group_type,
                CASE
                    WHEN COUNT(s.id) > 0 AND COALESCE(MAX(s.sale_date), c.created_at) < DATE('now', '-30 days') THEN 'Inactive'
                    WHEN COUNT(s.id) = 0 AND c.created_at < DATE('now', '-30 days') THEN 'Inactive'
                    ELSE 'Active'
                END AS activity_status
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id AND s.business_id = c.business_id
            WHERE c.business_id = %s
            GROUP BY c.id
            """,
            (biz_id,),
        )

        return jsonify({
            "business_info": biz_info,
            "filter_info": {
                "date_range": date_range,
                "start_date": start_date,
                "end_date": end_date,
            },
            "profit_report": {
                "total_sales": total_sales,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "profit_margin": profit_margin,
            },
            "sales_report": {
                "total_sales": total_sales,
                "invoice_count": sales_summary["invoice_count"] or 0,
                "avg_invoice": float(sales_summary["avg_invoice"] or 0),
                "top_products": top_selling_products,
                "invoices": period_invoices,
            },
            "expense_report": {
                "total_expenses": total_expenses,
                "expense_count": expense_summary["expense_count"] or 0,
                "avg_expense": float(expense_summary["avg_expense"] or 0),
                "highest_category": top_expense_category["category"] if top_expense_category else "None",
                "categories": expenses_by_category,
                "expenses": period_expenses,
            },
            "customer_report": {
                "total_customers": total_customers,
                "top_customers": top_customers,
            },
            "inventory_report": {
                "total_products": inv_summary["total_products"] or 0,
                "total_stock_units": inv_summary["total_stock_units"] or 0,
                "total_inventory_value": float(inv_summary["total_inventory_value"] or 0),
                "low_stock_count": inv_summary["low_stock_count"] or 0,
                "out_of_stock_count": inv_summary["out_of_stock_count"] or 0,
                "products": products_table,
            },
            "hr_report": {
                "total_employees": hr_summary["total_employees"] or 0,
                "active_employees": hr_summary["active_employees"] or 0,
                "inactive_employees": hr_summary["inactive_employees"] or 0,
                "total_departments": total_depts,
                "total_payroll": float(hr_summary["total_payroll"] or 0),
                "average_salary": float(hr_summary["average_salary"] or 0),
                "departments": departments_table,
            },
            "communication_report": {
                "total_messages": messages_stats["total_messages"] or 0,
                "sent_count": messages_stats["sent_count"] or 0,
                "scheduled_count": messages_stats["scheduled_count"] or 0,
                "failed_count": messages_stats["failed_count"] or 0,
            },
            "retention_report": {
                "customers": retention_customers,
                "new_count": sum(1 for c in retention_customers if c["group_type"] == "New"),
                "returning_count": sum(1 for c in retention_customers if c["group_type"] == "Returning"),
                "inactive_count": sum(1 for c in retention_customers if c["activity_status"] == "Inactive"),
            },
        })
    except DatabaseError as exc:
        return handle_db_error(exc)



