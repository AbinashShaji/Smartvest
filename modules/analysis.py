"""
analysis.py
-----------
Purpose : Handles the Dashboard and Analysis pages + their data APIs.
          ALL financial data now comes from the SQLite database — no more config lists.
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for
import config
from utils.db import get_db_connection   # ← real database helper

# Create the Analysis Blueprint so Flask can register these routes
analysis_bp = Blueprint('analysis', __name__)


# =============================================================================
# UI PAGE ROUTES  (return HTML pages)
# =============================================================================

@analysis_bp.route("/dashboard")
def dashboard():
    """
    Purpose : Renders the central Intelligence Dashboard page.
    Input   : None  (user_id is taken from the session automatically)
    Output  : HTML page, or redirect to login if not logged in.
    """
    # Safety check — only logged-in users can see the dashboard
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/dashboard.html",
        active_page="dashboard",
        user=config.get_current_user()
    )


@analysis_bp.route("/analysis")
def analysis_page():
    """
    Purpose : Renders the Financial Efficiency Report page.
    Input   : None
    Output  : HTML page, or redirect to login if not logged in.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/analysis.html",
        active_page="analysis",
        user=config.get_current_user()
    )


# =============================================================================
# ANALYSIS API ROUTES  (return JSON data for the frontend charts/cards)
# =============================================================================

@analysis_bp.route("/api/analysis/data")
def api_dashboard_data():
    """
    Purpose : Calculates high-level financial metrics for the logged-in user.
              Reads expenses and income from the SQLite database.
    Input   : None  (user_id comes from session)
    Output  : JSON with total_expenses, total_savings, goal_progress, username.
    """
    # Step 1: Make sure user is logged in
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Step 2: Get the integer user_id from the session
        user_id = config.get_current_user()["user_id"]

        # Step 3: Open a database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Step 4: Fetch ALL expenses that belong to this user
        cursor.execute(
            "SELECT amount FROM expenses WHERE user_id = ?",
            (user_id,)
        )
        expense_rows = cursor.fetchall()   # Returns a list of rows

        # Step 5: Add up all expense amounts using a simple loop
        total_expenses = 0.0
        for row in expense_rows:
            total_expenses = total_expenses + row["amount"]

        # Step 6: Fetch this user's monthly income (most recent record)
        cursor.execute(
            "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        income_row = cursor.fetchone()

        # Step 7: If no income record found, treat income as 0
        if income_row is not None:
            monthly_income = income_row["amount"]
        else:
            monthly_income = 0.0

        # Fetch goals from database using user_id
        cursor.execute(
            "SELECT target_amount, saved_amount FROM goals WHERE user_id = ?",
            (user_id,)
        )
        goal_rows = cursor.fetchall()
        
        # Add up all targets and saved amounts
        total_target = 0.0
        total_saved = 0.0
        for row in goal_rows:
            total_target = total_target + row["target_amount"]
            total_saved = total_saved + row["saved_amount"]

        # Step 8: Close the database — we are done reading
        conn.close()

        # Step 9: Calculate savings (cannot go below zero)
        total_savings = monthly_income - total_expenses
        if total_savings < 0:
            total_savings = 0.0

        # Calculate progress safely (handle division by zero if target_amount is 0)
        if total_target > 0:
            goal_progress = (total_saved / total_target) * 100
        else:
            goal_progress = 0.0

        # Step 10: Return the results as JSON
        return jsonify({
            "status": "success",
            "data": {
                "total_expenses": round(total_expenses, 2),
                "total_savings":  round(total_savings, 2),
                "goal_progress":  round(goal_progress),
                "alert_count":    0,
                "monthly_income": round(monthly_income, 2),
                "username": config.get_current_user()["username"],
            }
        })

    except Exception as e:
        # If anything goes wrong, return the error message so we can debug it
        return jsonify({"status": "error", "message": str(e)}), 400


@analysis_bp.route("/api/analysis/report")
def api_expense_analysis():
    """
    Purpose : Generates a savings-efficiency report for the logged-in user.
              Reads expenses and income from the SQLite database.
    Input   : None  (user_id comes from session)
    Output  : JSON with a summary sentence, total_expenses, and income.
    """
    # Step 1: Verify the user is logged in
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Step 2: Get the integer user_id from the session
        user_id = config.get_current_user()["user_id"]

        # Step 3: Open a database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Step 4: Fetch all expense amounts for this user
        cursor.execute(
            "SELECT amount FROM expenses WHERE user_id = ?",
            (user_id,)
        )
        expense_rows = cursor.fetchall()

        # Step 5: Sum up the expenses using a plain loop
        total_expenses = 0.0
        for row in expense_rows:
            total_expenses = total_expenses + row["amount"]

        # Step 6: Fetch the user's most recent monthly income
        cursor.execute(
            "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        income_row = cursor.fetchone()

        # Step 7: Default income to 0 when no data exists
        if income_row is not None:
            monthly_income = income_row["amount"]
        else:
            monthly_income = 0.0

        # Step 8: Close the database connection
        conn.close()

        # Step 9: Calculate savings rate as a percentage
        # Formula: savings_rate = ((income - expenses) / income) * 100
        if monthly_income > 0:
            savings_rate = ((monthly_income - total_expenses) / monthly_income) * 100
        else:
            savings_rate = 0.0

        # Savings rate cannot be negative (you can't save negative money in this display)
        if savings_rate < 0:
            savings_rate = 0.0

        # Step 10: Build a plain-English summary sentence
        summary_text = f"You are currently saving {savings_rate:.0f}% of your monthly income."

        # Step 11: Return the data as JSON
        return jsonify({
            "status": "success",
            "data": {
                "summary":        summary_text,
                "total_expenses": round(total_expenses, 2),
                "income":         round(monthly_income, 2),
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
