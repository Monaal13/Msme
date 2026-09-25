from flask import Blueprint, jsonify, request

from services.db import execute, fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

expenses_bp = Blueprint("expenses", __name__)


def validate_expense_data(data):
    title = (data.get("title") or "").strip()
    if not title:
        return "Expense title/description is required"
    category = (data.get("category") or "").strip()
    if not category:
        return "Category is required"
    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return "Expense amount must be greater than zero"
    except (ValueError, TypeError):
        return "Invalid expense amount format"
    return None


@expenses_bp.get("")
@login_required
def list_expenses():
    search = f"%{request.args.get('search', '').strip()}%"
    category = request.args.get("category", "").strip()
    date_range = request.args.get("date_range", "all").strip().lower()
    biz_id = current_business_id()

    query = """
        SELECT * FROM expenses
        WHERE business_id = %s
          AND (title LIKE %s OR category LIKE %s OR notes LIKE %s)
    """
    params = [biz_id, search, search, search]

    if category:
        query += " AND category = %s"
        params.append(category)

    if date_range == "this_month":
        query += " AND strftime('%Y-%m', COALESCE(expense_date, created_at)) = strftime('%Y-%m', 'now')"
    elif date_range == "last_month":
        query += " AND strftime('%Y-%m', COALESCE(expense_date, created_at)) = strftime('%Y-%m', 'now', '-1 month')"

    query += " ORDER BY COALESCE(expense_date, created_at) DESC, id DESC"

    try:
        return jsonify(fetch_all(query, tuple(params)))
    except DatabaseError as exc:
        return handle_db_error(exc)


@expenses_bp.get("/stats")
@login_required
def expense_stats():
    biz_id = current_business_id()
    try:
        stats = fetch_one(
            """
            SELECT
                COALESCE(SUM(amount), 0) AS total_expenses,
                COALESCE(SUM(CASE WHEN strftime('%Y-%m', COALESCE(expense_date, created_at)) = strftime('%Y-%m', 'now') THEN amount ELSE 0 END), 0) AS this_month_expenses,
                COALESCE(SUM(CASE WHEN strftime('%Y-%m', COALESCE(expense_date, created_at)) = strftime('%Y-%m', 'now', '-1 month') THEN amount ELSE 0 END), 0) AS last_month_expenses,
                COUNT(id) AS total_count,
                COALESCE(AVG(amount), 0) AS average_expense
            FROM expenses
            WHERE business_id = %s
            """,
            (biz_id,),
        )
        top_cat_row = fetch_one(
            """
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            WHERE business_id = %s AND category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY cat_total DESC
            LIMIT 1
            """,
            (biz_id,),
        )
        res = dict(stats) if stats else {
            "total_expenses": 0,
            "this_month_expenses": 0,
            "last_month_expenses": 0,
            "total_count": 0,
            "average_expense": 0,
        }
        res["highest_category"] = top_cat_row["category"] if top_cat_row else "None"
        return jsonify(res)
    except DatabaseError as exc:
        return handle_db_error(exc)


@expenses_bp.post("")
@login_required
def create_expense():
    data = request.get_json() or {}
    error = validate_expense_data(data)
    if error:
        return jsonify({"error": error}), 400
    biz_id = current_business_id()
    try:
        expense_id = execute(
            """
            INSERT INTO expenses (business_id, title, category, amount, expense_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                biz_id,
                data["title"].strip(),
                data["category"].strip(),
                float(data["amount"]),
                data.get("expense_date", "").strip() or None,
                data.get("notes", "").strip() or None,
            ),
        )
        return jsonify({"message": "Expense created successfully", "id": expense_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@expenses_bp.get("/<int:expense_id>")
@login_required
def get_expense(expense_id):
    biz_id = current_business_id()
    try:
        expense = fetch_one("SELECT * FROM expenses WHERE id = %s AND business_id = %s", (expense_id, biz_id))
        if not expense:
            return jsonify({"error": "Expense record not found"}), 404
        return jsonify(expense)
    except DatabaseError as exc:
        return handle_db_error(exc)


@expenses_bp.put("/<int:expense_id>")
@login_required
def update_expense(expense_id):
    data = request.get_json() or {}
    error = validate_expense_data(data)
    if error:
        return jsonify({"error": error}), 400
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM expenses WHERE id = %s AND business_id = %s", (expense_id, biz_id))
        if not existing:
            return jsonify({"error": "Expense record not found"}), 404

        execute(
            """
            UPDATE expenses
            SET title = %s, category = %s, amount = %s, expense_date = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                data["title"].strip(),
                data["category"].strip(),
                float(data["amount"]),
                data.get("expense_date", "").strip() or None,
                data.get("notes", "").strip() or None,
                expense_id,
                biz_id,
            ),
        )
        return jsonify({"message": "Expense updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@expenses_bp.delete("/<int:expense_id>")
@login_required
def delete_expense(expense_id):
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM expenses WHERE id = %s AND business_id = %s", (expense_id, biz_id))
        if not existing:
            return jsonify({"error": "Expense record not found"}), 404

        execute("DELETE FROM expenses WHERE id = %s AND business_id = %s", (expense_id, biz_id))
        return jsonify({"message": "Expense deleted successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)

