from datetime import datetime
from flask import Blueprint, jsonify, request

from services.db import db_cursor, fetch_all, fetch_one, normalize_query
from .common import DatabaseError, current_business_id, handle_db_error, login_required

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.get("")
@login_required
def list_attendance():
    target_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d")).strip()
    biz_id = current_business_id()
    try:
        # Fetch all active employees with their attendance for target_date
        records = fetch_all(
            """
            SELECT e.id AS employee_id, e.name AS employee_name, e.designation, d.name AS department_name,
                   COALESCE(a.status, 'Present') AS status, a.notes, a.date AS record_date, a.id AS attendance_id
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
            LEFT JOIN attendance a ON a.employee_id = e.id AND a.date = %s AND a.business_id = e.business_id
            WHERE e.business_id = %s AND LOWER(e.status) = 'active'
            ORDER BY d.name ASC, e.name ASC
            """,
            (target_date, biz_id),
        )
        return jsonify({"date": target_date, "records": records})
    except DatabaseError as exc:
        return handle_db_error(exc)


@attendance_bp.post("")
@login_required
def save_attendance():
    data = request.get_json() or {}
    biz_id = current_business_id()
    target_date = (data.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
    entries = data.get("attendance") or []

    if not entries:
        return jsonify({"error": "Attendance entries list is required"}), 400

    try:
        with db_cursor(commit=True) as cursor:
            for item in entries:
                emp_id = item.get("employee_id")
                status = (item.get("status") or "Present").strip()
                notes = (item.get("notes") or "").strip() or None

                if emp_id:
                    cursor.execute(
                        normalize_query("""
                        INSERT INTO attendance (business_id, employee_id, date, status, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT(business_id, employee_id, date) DO UPDATE SET
                            status = excluded.status,
                            notes = excluded.notes
                        """),
                        (biz_id, emp_id, target_date, status, notes),
                    )

        return jsonify({"message": f"Attendance recorded for {len(entries)} worker(s) on {target_date}"})
    except DatabaseError as exc:
        return handle_db_error(exc)
