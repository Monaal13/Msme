from flask import Blueprint, jsonify

from services.db import fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

analytics_bp = Blueprint("analytics", __name__)


def get_dashboard_data(business_id):
    summary_data = {
        "total_sales": fetch_one("SELECT COALESCE(SUM(total_amount), 0) AS value FROM sales WHERE business_id = %s", (business_id,))["value"],
        "total_expenses": fetch_one("SELECT COALESCE(SUM(amount), 0) AS value FROM expenses WHERE business_id = %s", (business_id,))["value"],
        "total_customers": fetch_one("SELECT COUNT(*) AS value FROM customers WHERE business_id = %s", (business_id,))["value"],
        "total_products": fetch_one("SELECT COUNT(*) AS value FROM products WHERE business_id = %s", (business_id,))["value"],
        "low_stock_items": fetch_one(
            "SELECT COUNT(*) AS value FROM inventory WHERE business_id = %s AND quantity <= minimum_stock_level",
            (business_id,),
        )["value"],
        "total_employees": fetch_one("SELECT COUNT(*) AS value FROM employees WHERE business_id = %s", (business_id,))["value"],
        "total_paid_amount": fetch_one(
            "SELECT COALESCE(SUM(total_amount), 0) AS value FROM sales WHERE business_id = %s AND LOWER(payment_status) = 'paid'",
            (business_id,),
        )["value"],
        "total_unpaid_amount": fetch_one(
            "SELECT COALESCE(SUM(total_amount), 0) AS value FROM sales WHERE business_id = %s AND LOWER(payment_status) != 'paid'",
            (business_id,),
        )["value"],
        "overdue_payments_count": fetch_one(
            "SELECT COUNT(*) AS value FROM sales WHERE business_id = %s AND LOWER(payment_status) != 'paid' AND due_date IS NOT NULL AND DATE(due_date) < DATE('now', 'localtime')",
            (business_id,),
        )["value"],
        "sales_today": fetch_one(
            "SELECT COUNT(*) AS value FROM sales WHERE business_id = %s AND DATE(sale_date) = DATE('now', 'localtime')",
            (business_id,),
        )["value"],
        # Manufacturing specific KPIs
        "today_orders": fetch_one(
            "SELECT COUNT(*) AS value FROM production_orders WHERE business_id = %s AND DATE(created_at) = DATE('now', 'localtime')",
            (business_id,),
        )["value"],
        "pending_orders": fetch_one(
            "SELECT COUNT(*) AS value FROM production_orders WHERE business_id = %s AND LOWER(status) NOT IN ('completed', 'cancelled', 'dispatched')",
            (business_id,),
        )["value"],
        "active_production": fetch_one(
            "SELECT COUNT(*) AS value FROM production_orders WHERE business_id = %s AND LOWER(current_stage) IN ('cutting', 'stitching', 'finishing')",
            (business_id,),
        )["value"],
        "orders_ready_dispatch": fetch_one(
            "SELECT COUNT(*) AS value FROM production_orders WHERE business_id = %s AND LOWER(current_stage) = 'ready for dispatch'",
            (business_id,),
        )["value"],
        "raw_material_low_stock": fetch_one(
            "SELECT COUNT(*) AS value FROM raw_materials WHERE business_id = %s AND current_stock <= minimum_stock",
            (business_id,),
        )["value"],
        "finished_goods_stock": fetch_one(
            "SELECT COALESCE(SUM(quantity), 0) AS value FROM inventory WHERE business_id = %s",
            (business_id,),
        )["value"],
    }
    summary_data["total_profit"] = float(summary_data["total_sales"]) - float(summary_data["total_expenses"])

    stage_counts_rows = fetch_all(
        """
        SELECT current_stage, COUNT(*) AS count
        FROM production_orders
        WHERE business_id = %s AND LOWER(status) != 'cancelled'
        GROUP BY current_stage
        """,
        (business_id,),
    )
    stage_counts = {r["current_stage"]: r["count"] for r in stage_counts_rows}

    monthly_sales = fetch_all(
        """
        SELECT strftime('%Y-%m', COALESCE(sale_date, created_at)) AS month, COALESCE(SUM(total_amount), 0) AS total
        FROM sales
        WHERE business_id = %s
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
        """,
        (business_id,),
    )
    monthly_sales.reverse()

    monthly_expenses = fetch_all(
        """
        SELECT strftime('%Y-%m', COALESCE(expense_date, created_at)) AS month, COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE business_id = %s
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
        """,
        (business_id,),
    )
    monthly_expenses.reverse()

    sales_by_month = {row["month"]: float(row["total"] or 0) for row in monthly_sales if row.get("month")}
    expenses_by_month = {row["month"]: float(row["total"] or 0) for row in monthly_expenses if row.get("month")}
    profit_months = sorted(set(sales_by_month) | set(expenses_by_month))[-12:]
    monthly_profit = [
        {
            "month": month,
            "total": sales_by_month.get(month, 0) - expenses_by_month.get(month, 0),
        }
        for month in profit_months
    ]

    recent_orders = fetch_all(
        """
        SELECT po.id, po.order_number, c.name AS customer_name, po.garment_name, po.quantity, po.current_stage, po.status, po.created_at
        FROM production_orders po
        JOIN customers c ON c.id = po.customer_id AND c.business_id = po.business_id
        WHERE po.business_id = %s
        ORDER BY po.created_at DESC
        LIMIT 8
        """,
        (business_id,),
    )

    raw_material_shortages = fetch_all(
        """
        SELECT name, category, current_stock, minimum_stock, unit,
               (minimum_stock - current_stock) AS shortage_qty
        FROM raw_materials
        WHERE business_id = %s AND current_stock <= minimum_stock
        ORDER BY current_stock ASC
        LIMIT 8
        """,
        (business_id,),
    )

    return {
        "summary": summary_data,
        "stage_counts": stage_counts,
        "monthly_sales": monthly_sales,
        "monthly_expenses": monthly_expenses,
        "monthly_profit": monthly_profit,
        "recent_orders": recent_orders,
        "raw_material_shortages": raw_material_shortages,
    }


@analytics_bp.get("/dashboard")
@login_required
def dashboard():
    try:
        return jsonify(get_dashboard_data(current_business_id()))
    except DatabaseError as exc:
        return handle_db_error(exc)


@analytics_bp.get("/summary")
@login_required
def summary():
    try:
        return jsonify(get_dashboard_data(current_business_id())["summary"])
    except DatabaseError as exc:
        return handle_db_error(exc)


@analytics_bp.get("/charts")
@login_required
def charts():
    try:
        business_id = current_business_id()
        sales_by_month = fetch_all(
            """
            SELECT strftime('%Y-%m', COALESCE(sale_date, created_at)) AS month, COALESCE(SUM(total_amount), 0) AS total
            FROM sales WHERE business_id = %s
            GROUP BY month ORDER BY month
            """,
            (business_id,),
        )
        expenses_by_month = fetch_all(
            """
            SELECT strftime('%Y-%m', COALESCE(expense_date, created_at)) AS month, COALESCE(SUM(amount), 0) AS total
            FROM expenses WHERE business_id = %s
            GROUP BY month ORDER BY month
            """,
            (business_id,),
        )
        top_products = fetch_all(
            """
            SELECT p.name, COALESCE(SUM(si.quantity), 0) AS quantity_sold
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            JOIN sales s ON s.id = si.sale_id
            WHERE s.business_id = %s
            GROUP BY p.id, p.name
            ORDER BY quantity_sold DESC
            LIMIT 5
            """,
            (business_id,),
        )
        return jsonify({"sales_by_month": sales_by_month, "expenses_by_month": expenses_by_month, "top_products": top_products})
    except DatabaseError as exc:
        return handle_db_error(exc)
