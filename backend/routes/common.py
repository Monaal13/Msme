from functools import wraps
import sqlite3

from flask import current_app, jsonify, session


def current_business_id():
    return session.get("business_id")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required"}), 401
        if session.get("role") == "customer" or not session.get("business_id"):
            return jsonify({"error": "Administrator or staff access required"}), 403
        from services.db import fetch_one
        user = fetch_one("SELECT is_active FROM users WHERE id = %s", (session.get("user_id"),))
        if not user or not user.get("is_active", 1):
            session.clear()
            return jsonify({"error": "Your account has been deactivated. Please contact the administrator."}), 403
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"error": "Administrator access required"}), 403
        return view(*args, **kwargs)

    return wrapped


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required"}), 401
        if session.get("role") != "customer":
            return jsonify({"error": "Customer account required"}), 403
        from services.db import fetch_one
        link = fetch_one(
            """SELECT cu.business_id FROM customer_users cu
               JOIN customers c ON c.id = cu.customer_id AND c.business_id = cu.business_id
               JOIN users u ON u.id = cu.user_id
               WHERE cu.user_id = %s AND u.is_active = 1
                 AND LOWER(COALESCE(c.status, 'active')) = 'active' LIMIT 1""",
            (session.get("user_id"),),
        )
        if not link:
            session.clear()
            return jsonify({"error": "Your account is not registered with this company. Please contact the administrator."}), 403
        return view(*args, **kwargs)

    return wrapped


def handle_db_error(error):
    current_app.logger.exception(
        "SQLite error: type=%s message=%s",
        type(error).__name__,
        getattr(error, "msg", str(error)),
    )
    return jsonify({"error": "Database operation failed. Check the Flask terminal for the safe SQLite error."}), 500


DatabaseError = sqlite3.Error


def require_fields(data, fields):
    missing = [field for field in fields if not data.get(field)]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None
