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
