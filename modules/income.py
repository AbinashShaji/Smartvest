"""
income.py
---------
Purpose : Minimal single-value monthly income storage and API.
          Uses the existing SQLite income table without changing schema.
"""

from flask import Blueprint, jsonify, request
import config
from utils.db import get_db_connection
from datetime import datetime

income_bp = Blueprint("income", __name__)


def _coerce_amount(amount):
    """Validate and normalize income input as a non-negative float."""
    if amount in (None, ""):
        raise ValueError("Income amount is required.")

    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Income must be a valid number.")

    if value < 0:
        raise ValueError("Income cannot be negative.")

    return value


def set_income(amount):
    """
    Store a single monthly income value for the logged-in user.
    Returns a dict with the saved amount.
    """
    if not config.is_logged_in():
        raise PermissionError("Login required")

    amount_value = _coerce_amount(amount)
    user_id = config.get_current_user()["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
    cursor.execute(
        "INSERT INTO income (user_id, amount, source, date) VALUES (?, ?, ?, ?)",
        (user_id, amount_value, "Monthly", datetime.now().strftime("%Y-%m-%d")),
    )
    conn.commit()
    conn.close()

    return {"income": amount_value}


def get_income():
    """
    Retrieve the current monthly income for the logged-in user.
    Returns a dict with amount and state.
    """
    if not config.is_logged_in():
        raise PermissionError("Login required")

    user_id = config.get_current_user()["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT amount, date, source FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {"income": 0.0, "is_empty": True}

    try:
        amount_value = float(row["amount"])
    except (TypeError, ValueError):
        amount_value = 0.0

    return {
        "income": amount_value,
        "date": row["date"],
        "source": row["source"],
        "is_empty": False,
    }


@income_bp.route("/api/income/set", methods=["POST"])
def api_set_income():
    """Set or replace the current monthly income."""
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    try:
        result = set_income(data.get("amount"))
        return jsonify({"status": "success", "data": result})
    except (ValueError, PermissionError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@income_bp.route("/api/income/get")
def api_get_income():
    """Get the current monthly income."""
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        result = get_income()
        return jsonify({"status": "success", "data": result})
    except PermissionError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 401
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
