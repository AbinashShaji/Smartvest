from flask import Blueprint, render_template, jsonify, redirect, url_for
import config

# Create the Analysis Blueprint
analysis_bp = Blueprint('analysis', __name__)

# --- UI PAGE ROUTES (HTML) ---

@analysis_bp.route("/dashboard")
def dashboard():
    """
    Purpose: Renders the central Intelligence Dashboard.
    Input: None
    Output: HTML template or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
        
    return render_template("user/dashboard.html", active_page="dashboard", user=config.get_current_user())

@analysis_bp.route("/analysis")
def analysis_page():
    """
    Purpose: Renders the specialized financial efficiency report page.
    Input: None
    Output: HTML template or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
        
    return render_template("user/analysis.html", active_page="analysis", user=config.get_current_user())


# --- ANALYSIS API ROUTES (PROTECTED) ---

@analysis_bp.route("/api/analysis/data")
def api_dashboard_data():
    """
    Purpose: Calculates high-level financial metrics for the current session user.
    Input: None
    Output: JSON with total expenses, savings, and progress.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        
        total_expenses = sum(item["amount"] for item in config.EXPENSES if item.get("user_id") == user_id)
        user_inc = config.INCOME["monthly"] if config.INCOME.get("user_id") == user_id else 0
        total_savings = max(user_inc - total_expenses, 0)
        
        return jsonify({
            "status": "success",
            "data": {
                "total_expenses": round(total_expenses, 2),
                "total_savings": round(total_savings, 2),
                "goal_progress": 65, # Mock value for frontend visualization
                "username": config.get_current_user()["username"],
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@analysis_bp.route("/api/analysis/report")
def api_expense_analysis():
    """
    Purpose: Generates a detailed breakdown of savings efficiency.
    Input: None
    Output: JSON summary text and raw data.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        total_expenses = sum(item["amount"] for item in config.EXPENSES if item.get("user_id") == user_id)
        user_inc = config.INCOME["monthly"] if config.INCOME.get("user_id") == user_id else 1
        
        savings_rate = max(((user_inc - total_expenses) / user_inc) * 100, 0)
        summary_text = f"You are currently saving {savings_rate:.0f}% of your monthly income."
        
        return jsonify({
            "status": "success",
            "data": {
                "summary": summary_text,
                "total_expenses": total_expenses,
                "income": user_inc,
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
