from flask import Blueprint, jsonify, request

from services.db import execute, fetch_all, fetch_one
from .common import DatabaseError, current_business_id, handle_db_error, login_required

departments_bp = Blueprint("departments", __name__)


@departments_bp.get("")
@login_required
def list_departments():
    biz_id = current_business_id()
    try:
        departments = fetch_all(
            """
            SELECT d.*, COUNT(e.id) AS employee_count
            FROM departments d
            LEFT JOIN employees e ON e.department_id = d.id AND e.business_id = d.business_id
            WHERE d.business_id = %s
            GROUP BY d.id
            ORDER BY d.name ASC
            """,
            (biz_id,),
        )
        return jsonify(departments)
    except DatabaseError as exc:
        return handle_db_error(exc)


@departments_bp.post("")
@login_required
def create_department():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Department name is required"}), 400

    biz_id = current_business_id()
    status_val = (data.get("status") or "active").strip().lower()
    try:
        department_id = execute(
            "INSERT INTO departments (business_id, name, description, status) VALUES (%s, %s, %s, %s)",
            (biz_id, name, (data.get("description") or "").strip() or None, status_val),
        )
        return jsonify({"message": "Department created successfully", "id": department_id}), 201
    except DatabaseError as exc:
        return handle_db_error(exc)


@departments_bp.get("/<int:department_id>")
@login_required
def get_department(department_id):
    biz_id = current_business_id()
    try:
        dept = fetch_one(
            """
            SELECT d.*, COUNT(e.id) AS employee_count
            FROM departments d
            LEFT JOIN employees e ON e.department_id = d.id AND e.business_id = d.business_id
            WHERE d.id = %s AND d.business_id = %s
            GROUP BY d.id
            """,
            (department_id, biz_id),
        )
        if not dept:
            return jsonify({"error": "Department not found"}), 404
        return jsonify(dept)
    except DatabaseError as exc:
        return handle_db_error(exc)


@departments_bp.put("/<int:department_id>")
@login_required
def update_department(department_id):
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Department name is required"}), 400

    biz_id = current_business_id()
    status_val = (data.get("status") or "active").strip().lower()
    try:
        dept = fetch_one("SELECT id FROM departments WHERE id = %s AND business_id = %s", (department_id, biz_id))
        if not dept:
            return jsonify({"error": "Department not found"}), 404

        execute(
            "UPDATE departments SET name = %s, description = %s, status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND business_id = %s",
            (name, (data.get("description") or "").strip() or None, status_val, department_id, biz_id),
        )
        return jsonify({"message": "Department updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)


@departments_bp.delete("/<int:department_id>")
@login_required
def delete_department(department_id):
    biz_id = current_business_id()
    try:
        dept = fetch_one("SELECT * FROM departments WHERE id = %s AND business_id = %s", (department_id, biz_id))
        if not dept:
            return jsonify({"error": "Department not found"}), 404

        emp_count_row = fetch_one(
            "SELECT COUNT(*) AS count FROM employees WHERE department_id = %s AND business_id = %s",
            (department_id, biz_id),
        )
        emp_count = emp_count_row["count"] if emp_count_row else 0
        if emp_count > 0:
            return jsonify({
                "error": f"Cannot delete department '{dept['name']}'. It currently has {emp_count} employee(s) assigned. Please reassign or remove those employees first."
            }), 400

        execute("DELETE FROM departments WHERE id = %s AND business_id = %s", (department_id, biz_id))
        return jsonify({"message": "Department deleted successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)

