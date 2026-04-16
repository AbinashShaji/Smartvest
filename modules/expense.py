from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime   # Used to get today's date automatically
import config
import csv
import io
from utils.db import get_db_connection

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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses WHERE user_id = ?", (user_id,))
        user_data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
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

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Amount must be a valid number."}), 400

        user_id = config.get_current_user()["user_id"]
        # Get today's date automatically — never hardcoded
        date = datetime.now().strftime("%Y-%m-%d")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount_value, category, date, description))
        conn.commit()
        
        # Retrieve the newly added record to return
        expense_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        new_entry = dict(cursor.fetchone())
        conn.close()

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

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Income must be a valid number."}), 400

        user_id = config.get_current_user()["user_id"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM income WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("UPDATE income SET amount = ? WHERE user_id = ?", (amount_value, user_id))
        else:
            cursor.execute("INSERT INTO income (user_id, amount, source, date) VALUES (?, ?, ?, ?)",
                         (user_id, amount_value, "Monthly", datetime.now().strftime("%Y-%m-%d")))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "data": {"income": amount_value}})
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals WHERE user_id = ?", (user_id,))
    user_goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
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

        try:
            target_value = float(target)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Goal target must be a valid number."}), 400

        user_id = config.get_current_user()["user_id"]
        deadline = data.get("deadline") or ""
        saved = 0

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goals (user_id, goal_name, target_amount, saved_amount, deadline)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, target_value, saved, deadline))
        conn.commit()
        
        goal_id = cursor.lastrowid
        cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        new_goal = dict(cursor.fetchone())
        conn.close()

        return jsonify({"status": "success", "data": new_goal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# --- CSV TOOLS (PROTECTED) ---

@expense_bp.route("/api/expense/upload", methods=["POST"])
def api_upload_csv():
    """
    Purpose: Handles CSV file processing and saves data to database.
    Input: multipart/form-data (file)
    Output: Success message.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"status": "error", "message": "Please choose a CSV file."}), 400
    
    try:
        user_id = config.get_current_user()["user_id"]
        
        # Read the uploaded file as text
        stream = io.StringIO(uploaded.stream.read().decode("utf-8"), newline=None)
        
        # Parse CSV assuming headers: amount, category, date
        csv_reader = csv.DictReader(stream)
        
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Simple loop to read and insert each row
        for row in csv_reader:
            amount = row.get("amount")
            category = row.get("category")
            date = row.get("date")
            description = "CSV Import"  # Default generic description

            if amount in (None, ""):
                continue

            try:
                amount_value = float(amount)
            except (TypeError, ValueError):
                continue
            
            # Insert the row into the expenses table
            cursor.execute("""
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, amount_value, category, date, description))
            
        # Save all the new expenses
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "data": {"message": f"{uploaded.filename} uploaded and data saved successfully."}
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error saving data: {str(e)}"}), 400

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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT description, category, amount, date FROM expenses WHERE user_id = ?", (user_id,))
        expenses = cursor.fetchall()
        conn.close()
        
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["description", "category", "amount", "date"])
        
        for expense in expenses:
            writer.writerow([expense["description"], expense["category"], expense["amount"], expense["date"]])

        return csv_buffer.getvalue(), 200, {
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename=smartvest_export_user_{user_id}.csv",
        }
    except Exception:
        return "Error generating export.", 500
