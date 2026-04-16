from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import config
import csv
import io

# Create the Expense Blueprint
expense_bp = Blueprint('expense', __name__)

# --- UI PAGE ROUTES (HTML) ---

@expense_bp.route("/expenses")
def expenses():
    """
    Purpose: Renders the Manage Expenses page.
    Input: None
    Output: HTML template or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
        
    return render_template("user/expense.html", active_page="expenses", user=config.get_current_user())

@expense_bp.route("/goals")
def goals():
    """
    Purpose: Renders the Financial Goals page.
    Input: None
    Output: HTML template or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
        
    return render_template("user/goals.html", active_page="goals", user=config.get_current_user())


# --- EXPENSE API ROUTES (PROTECTED) ---

@expense_bp.route("/api/expense/all")
def api_expenses():
    """
    Purpose: Fetch all expenses for the currently logged-in user.
    Input: None (User ID pulled from session)
    Output: Standardized JSON list of expenses.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        # Only pull data belonging to the session user
        user_data = [exp for exp in config.EXPENSES if exp.get("user_id") == user_id]
        return jsonify({"status": "success", "data": user_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@expense_bp.route("/api/expense/add", methods=["POST"])
def api_add_expense():
    """
    Purpose: Add a new expense record tagged with the session user ID.
    Input: JSON (description, amount, category)
    Output: Newly created expense object.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        description = (data.get("description") or "").strip()
        category = (data.get("category") or "Other").strip()
        amount = data.get("amount")

        if not description or amount in (None, ""):
            return jsonify({"status": "error", "message": "Description and amount are required."}), 400

        new_entry = {
            "user_id": config.get_current_user()["user_id"],
            "description": description,
            "amount": float(amount),
            "category": category,
            "date": "2026-04-15",
        }
        
        config.EXPENSES.insert(0, new_entry)
        return jsonify({"status": "success", "data": new_entry})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@expense_bp.route("/api/expense/income/update", methods=["POST"])
def api_set_income():
    """
    Purpose: Updates the monthly income value for the logged-in user.
    Input: JSON (income)
    Output: Updated income object.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        amount = data.get("income")
        
        if amount in (None, ""):
            return jsonify({"status": "error", "message": "Income amount is required."}), 400

        config.INCOME["monthly"] = float(amount)
        config.INCOME["user_id"] = config.get_current_user()["user_id"]
        return jsonify({"status": "success", "data": {"income": config.INCOME["monthly"]}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# --- GOALS API ROUTES (PROTECTED) ---

@expense_bp.route("/api/expense/goal/all")
def api_goal_status():
    """
    Purpose: Retrieves all financial goals for the current user.
    Input: None
    Output: JSON list of goals.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    user_id = config.get_current_user()["user_id"]
    user_goals = [g for g in config.GOALS if g.get("user_id") == user_id]
    return jsonify({"status": "success", "data": user_goals})

@expense_bp.route("/api/expense/goal/add", methods=["POST"])
def api_set_goal():
    """
    Purpose: Creates a new financial goal associated with the session user.
    Input: JSON (name, target, deadline)
    Output: Created goal object.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        target = data.get("target")

        if not name or target in (None, ""):
            return jsonify({"status": "error", "message": "Goal name and target are required."}), 400

        new_goal = {
            "user_id": config.get_current_user()["user_id"],
            "name": name,
            "target": float(target),
            "deadline": data.get("deadline") or "",
            "saved": 0,
        }
        config.GOALS.insert(0, new_goal)
        return jsonify({"status": "success", "data": new_goal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# --- CSV TOOLS (PROTECTED) ---

@expense_bp.route("/api/expense/upload", methods=["POST"])
def api_upload_csv():
    """
    Purpose: Handles CSV file processing.
    Input: multipart/form-data (file)
    Output: Success message.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"status": "error", "message": "Please choose a CSV file."}), 400
    
    return jsonify({"status": "success", "data": {"message": f"{uploaded.filename} uploaded successfully."}})

@expense_bp.route("/api/expense/export")
def api_export_data():
    """
    Purpose: Exports user expenses as a downloadable CSV.
    Input: None
    Output: CSV text/binary file.
    """
    if not config.is_logged_in():
        return "Authentication required.", 401

    try:
        user_id = config.get_current_user()["user_id"]
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["description", "category", "amount", "date"])
        
        for expense in config.EXPENSES:
            if expense.get("user_id") == user_id:
                writer.writerow([expense["description"], expense["category"], expense["amount"], expense["date"]])

        return csv_buffer.getvalue(), 200, {
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename=smartvest_export_user_{user_id}.csv",
        }
    except Exception:
        return "Error generating export.", 500
