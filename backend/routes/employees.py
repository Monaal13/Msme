import re
from flask import Blueprint, jsonify, request

from services.db import execute, fetch_all, fetch_one
from .common import DatabaseError, admin_required, current_business_id, handle_db_error

employees_bp = Blueprint("employees", __name__)


def validate_employee_data(data, biz_id):
    name = (data.get("name") or "").strip()
    if not name:
        return "Employee name is required"

    email = (data.get("email") or "").strip()
    if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return "Invalid email address format"

    try:
        salary = float(data.get("salary", 0))
        if salary < 0:
            return "Salary cannot be negative"
    except (ValueError, TypeError):
        return "Invalid salary format"

    dept_id = data.get("department_id")
    status = (data.get("status") or "active").strip().lower()
    if status not in ("active", "inactive"):
        return "Employment status must be active or inactive"
    if dept_id:
        dept = fetch_one("SELECT id FROM departments WHERE id = %s AND business_id = %s", (dept_id, biz_id))
        if not dept:
            return "Selected department does not exist or does not belong to your business"

    return None


@employees_bp.get("")
@admin_required
def list_employees():
    search = f"%{request.args.get('search', '').strip()}%"
    status = request.args.get("status", "all").strip().lower()
    dept_id = request.args.get("department_id")
    biz_id = current_business_id()

    try:
        query = """
            SELECT e.*, d.name AS department_name
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id AND d.business_id = e.business_id
            WHERE e.business_id = %s
              AND (e.name LIKE %s OR e.phone LIKE %s OR e.email LIKE %s OR e.designation LIKE %s OR d.name LIKE %s)
        """
        params = [biz_id, search, search, search, search, search]

        if status in ("active", "inactive"):
            query += " AND LOWER(e.status) = %s"
            params.append(status)

        if dept_id:
            try:
                query += " AND e.department_id = %s"
                params.append(int(dept_id))
            except (ValueError, TypeError):
                pass

        query += " ORDER BY e.created_at DESC, e.id DESC"
        employees = fetch_all(query, tuple(params))
        return jsonify(employees)
    except DatabaseError as exc:
        return handle_db_error(exc)


@employees_bp.get("/stats")
@admin_required
def employee_stats():
    biz_id = current_business_id()
    try:
        stats = fetch_one(
            """
            SELECT
                COUNT(id) AS total_employees,
                COALESCE(SUM(CASE WHEN LOWER(status) = 'active' THEN 1 ELSE 0 END), 0) AS active_employees,
                COALESCE(SUM(CASE WHEN LOWER(status) = 'inactive' THEN 1 ELSE 0 END), 0) AS inactive_employees,
                COALESCE(SUM(salary), 0) AS total_payroll,
                COALESCE(AVG(salary), 0) AS average_salary
            FROM employees
            WHERE business_id = %s
            """,
            (biz_id,),
        )
        dept_stat = fetch_one(
            "SELECT COUNT(id) AS total_departments FROM departments WHERE business_id = %s",
            (biz_id,),
        )
        res = dict(stats) if stats else {
            "total_employees": 0,
            "active_employees": 0,
            "inactive_employees": 0,
            "total_payroll": 0,
            "average_salary": 0,
        }
        res["total_departments"] = dept_stat["total_departments"] if dept_stat else 0
        return jsonify(res)
    except DatabaseError as exc:
        return handle_db_error(exc)


@employees_bp.post("")
@admin_required
def create_employee():
    data = request.get_json() or {}
    biz_id = current_business_id()
    error = validate_employee_data(data, biz_id)
    if error:
        return jsonify({"error": error}), 400

    try:
        employee_id = execute(
            """
            INSERT INTO employees
            (business_id, department_id, name, phone, email, designation, salary, joining_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                biz_id,
                data.get("department_id") or None,
                data["name"].strip(),
                (data.get("phone") or "").strip() or None,
                (data.get("email") or "").strip() or None,
                (data.get("designation") or "").strip() or None,
                float(data.get("salary", 0)),
                (data.get("joining_date") or "").strip() or None,
                (data.get("status") or "active").strip().lower(),
            ),
        )
        return jsonify({"message": "Employee created successfully", "id": employee_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@employees_bp.get("/<int:employee_id>")
@admin_required
def get_employee(employee_id):
    biz_id = current_business_id()
    try:
        employee = fetch_one(
            """
            SELECT e.*, d.name AS department_name
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id AND d.business_id = e.business_id
            WHERE e.id = %s AND e.business_id = %s
            """,
            (employee_id, biz_id),
        )
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        return jsonify(employee)
    except DatabaseError as exc:
        return handle_db_error(exc)


@employees_bp.put("/<int:employee_id>")
@admin_required
def update_employee(employee_id):
    data = request.get_json() or {}
    biz_id = current_business_id()
    error = validate_employee_data(data, biz_id)
    if error:
        return jsonify({"error": error}), 400

    try:
        existing = fetch_one("SELECT id FROM employees WHERE id = %s AND business_id = %s", (employee_id, biz_id))
        if not existing:
            return jsonify({"error": "Employee not found"}), 404

        execute(
            """
            UPDATE employees
            SET department_id = %s, name = %s, phone = %s, email = %s, designation = %s,
                salary = %s, joining_date = %s, status = %s,
                leaving_date = CASE WHEN LOWER(%s) = 'active' THEN NULL WHEN leaving_date IS NULL THEN DATE('now') ELSE leaving_date END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (
                data.get("department_id") or None,
                data["name"].strip(),
                (data.get("phone") or "").strip() or None,
                (data.get("email") or "").strip() or None,
                (data.get("designation") or "").strip() or None,
                float(data.get("salary", 0)),
                (data.get("joining_date") or "").strip() or None,
                (data.get("status") or "active").strip().lower(),
                (data.get("status") or "active").strip().lower(),
                employee_id,
                biz_id,
            ),
        )
        return jsonify({"message": "Employee updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@employees_bp.delete("/<int:employee_id>")
@admin_required
def delete_employee(employee_id):
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM employees WHERE id = %s AND business_id = %s", (employee_id, biz_id))
        if not existing:
            return jsonify({"error": "Employee not found"}), 404

        execute("UPDATE employees SET status = 'inactive', leaving_date = COALESCE(leaving_date, DATE('now')), updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s", (employee_id, biz_id))
        return jsonify({"message": "Employee deactivated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@employees_bp.post("/<int:employee_id>/reactivate")
@admin_required
def reactivate_employee(employee_id):
    biz_id = current_business_id()
    try:
        existing = fetch_one("SELECT id FROM employees WHERE id = %s AND business_id = %s", (employee_id, biz_id))
        if not existing:
            return jsonify({"error": "Employee not found"}), 404
        execute("UPDATE employees SET status = 'active', leaving_date = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s", (employee_id, biz_id))
        return jsonify({"message": "Employee reactivated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)

