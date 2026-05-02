from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
import config
from utils.db import get_db_connection
from modules.analysis import get_analysis_data
from modules.goals import enrich_goal_rows, enrich_goal_row, build_goal_analysis

# Create the Expense Blueprint
expense_bp = Blueprint('expense', __name__)


def _expense_order_clause(cursor, preferred_columns=("created_at", "date", "id")):
    """
    Choose the safest ordering column that actually exists in the table.
    This keeps the query working even if the schema changes over time.
    """
    cursor.execute("PRAGMA table_info(expenses)")
    available = {row["name"] for row in cursor.fetchall()}

    for column in preferred_columns:
        if column in available:
            return column

    return "id"


def _fetch_user_expenses(user_id, limit=None):
    """
    Read expenses for one user.
    limit=None returns the full list.
    limit=5 returns only the latest five rows for dashboard recent activity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    order_column = _expense_order_clause(cursor)
    order_sql = f"{order_column} DESC, id DESC"
    sql = f"SELECT * FROM expenses WHERE user_id = ? ORDER BY {order_sql}"
    params = [user_id]

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# --- UI PAGE ROUTES (HTML) ---

@expense_bp.route("/expenses")
def expenses():
    """
    Purpose: Renders the Add Expense page.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/expense_add.html",
        active_page="expenses",
        user=config.get_current_user(),
        expense_page="add",
    )


@expense_bp.route("/expenses/add")
def expenses_add():
    """
    Purpose: Alias route for the Add Expense page.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/expense_add.html",
        active_page="expenses",
        user=config.get_current_user(),
        expense_page="add",
    )


@expense_bp.route("/expenses/list")
def expenses_list():
    """
    Purpose: Renders the Expense List page.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/expense_list.html",
        active_page="expenses",
        user=config.get_current_user(),
        expense_page="list",
    )


@expense_bp.route("/expenses/export")
def expenses_export():
    """
    Purpose: Renders the Export Expense page.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/expense_export.html",
        active_page="expenses",
        user=config.get_current_user(),
        expense_page="export",
    )


@expense_bp.route("/goals")
def goals():
    """
    Purpose: Renders the Financial Goals page.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template("user/goals.html", active_page="goals", user=config.get_current_user())


# --- EXPENSE API ROUTES (PROTECTED) ---

@expense_bp.route("/api/expense/all")
def api_expenses():
    """
    Purpose: Fetch all expenses for the currently logged-in user.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        user_data = _fetch_user_expenses(user_id)

        return jsonify({"status": "success", "data": user_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/recent")
def api_recent_expenses():
    """
    Purpose: Fetch the latest five individual expenses for dashboard recent activity.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        # Debug helper: keep this endpoint limited so the dashboard never renders the full history.
        recent_rows = _fetch_user_expenses(user_id, limit=5)
        return jsonify({"status": "success", "data": recent_rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/add", methods=["POST"])
def api_add_expense():
    """
    Purpose: Add a new expense record tagged with the session user ID.
    Input: JSON (amount, category, date, optional description)
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        description = (data.get("description") or "").strip()
        category = (data.get("category") or "Other").strip()
        amount = data.get("amount")
        date_value = (data.get("date") or "").strip()

        if amount in (None, ""):
            return jsonify({"status": "error", "message": "Amount is required."}), 400

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Amount must be a valid number."}), 400

        if not description:
            # Keep the row meaningful even when the UI does not ask for a note.
            description = category or "Expense"

        if date_value:
            try:
                datetime.strptime(date_value, "%Y-%m-%d")
            except ValueError:
                return jsonify({"status": "error", "message": "Date must be in YYYY-MM-DD format."}), 400
        else:
            date_value = datetime.now().strftime("%Y-%m-%d")

        user_id = config.get_current_user()["user_id"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, amount_value, category, date_value, description),
        )
        conn.commit()

        expense_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        new_entry = dict(cursor.fetchone())
        conn.close()

        return jsonify({"status": "success", "data": new_entry})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/delete", methods=["DELETE", "POST"])
def api_delete_expense():
    """
    Purpose: Delete an existing expense based on ID.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        expense_id = data.get("expense_id")
        user_id = config.get_current_user()["user_id"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Expense deleted"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/update", methods=["POST"])
def api_update_expense():
    """
    Purpose: Update an expense (amount, category, date).
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        expense_id = data.get("expense_id")
        amount = data.get("amount")
        category = data.get("category")
        date = data.get("date")

        user_id = config.get_current_user()["user_id"]

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Amount must be a valid number."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE expenses
            SET amount = ?, category = ?, date = ?
            WHERE id = ? AND user_id = ?
            """,
            (amount_value, category, date, expense_id, user_id),
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Expense updated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/income/update", methods=["POST"])
def api_set_income():
    """
    Purpose: Updates the monthly income value for the logged-in user.
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
            cursor.execute(
                "INSERT INTO income (user_id, amount, source, date) VALUES (?, ?, ?, ?)",
                (user_id, amount_value, "Monthly", datetime.now().strftime("%Y-%m-%d")),
            )

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
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    user_id = config.get_current_user()["user_id"]
    analysis_snapshot = get_analysis_data(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals WHERE user_id = ?", (user_id,))
    user_goals = [dict(row) for row in cursor.fetchall()]
    conn.close()

    enriched_goals = enrich_goal_rows(user_goals, analysis_snapshot=analysis_snapshot)
    return jsonify({"status": "success", "data": enriched_goals})


@expense_bp.route("/api/expense/goal/add", methods=["POST"])
def api_set_goal():
    """
    Purpose: Creates a new financial goal associated with the session user.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        target = data.get("target")
        saved = data.get("saved", 0)
        deadline = data.get("deadline") or ""

        if not name or target in (None, ""):
            return jsonify({"status": "error", "message": "Goal name and target are required."}), 400

        try:
            target_value = float(target)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Goal target must be a valid number."}), 400

        try:
            saved_value = float(saved)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Saved amount must be a valid number."}), 400

        if saved_value < 0:
            saved_value = 0.0

        if deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                return jsonify({"status": "error", "message": "Deadline must be in YYYY-MM-DD format."}), 400

        user_id = config.get_current_user()["user_id"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO goals (user_id, goal_name, target_amount, saved_amount, deadline)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, name, target_value, saved_value, deadline),
        )
        conn.commit()

        goal_id = cursor.lastrowid
        cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        new_goal = dict(cursor.fetchone())
        conn.close()

        analysis_snapshot = get_analysis_data(user_id)
        analysis = build_goal_analysis(user_id, analysis_snapshot=analysis_snapshot)
        return jsonify({"status": "success", "data": enrich_goal_row(new_goal, analysis)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/goal/update", methods=["POST"])
def api_update_goal():
    """
    Purpose: Updates an existing financial goal without changing the schema.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        goal_id = data.get("goal_id")
        name = (data.get("name") or "").strip()
        target = data.get("target")
        saved = data.get("saved", 0)
        deadline = data.get("deadline") or ""

        if goal_id in (None, ""):
            return jsonify({"status": "error", "message": "Goal ID is required."}), 400

        if not name or target in (None, ""):
            return jsonify({"status": "error", "message": "Goal name and target are required."}), 400

        try:
            target_value = float(target)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Goal target must be a valid number."}), 400

        try:
            saved_value = float(saved)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Saved amount must be a valid number."}), 400

        if saved_value < 0:
            saved_value = 0.0

        if deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                return jsonify({"status": "error", "message": "Deadline must be in YYYY-MM-DD format."}), 400

        user_id = config.get_current_user()["user_id"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE goals
            SET goal_name = ?, target_amount = ?, saved_amount = ?, deadline = ?
            WHERE id = ? AND user_id = ?
            """,
            (name, target_value, saved_value, deadline, goal_id, user_id),
        )
        conn.commit()
        cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        updated_goal = cursor.fetchone()
        conn.close()

        if updated_goal is None:
            return jsonify({"status": "error", "message": "Goal not found."}), 404

        analysis_snapshot = get_analysis_data(user_id)
        analysis = build_goal_analysis(user_id, analysis_snapshot=analysis_snapshot)
        return jsonify({"status": "success", "data": enrich_goal_row(dict(updated_goal), analysis)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@expense_bp.route("/api/expense/goal/delete", methods=["DELETE", "POST"])
def api_delete_goal():
    """
    Purpose: Deletes a goal for the active user without affecting the schema.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        goal_id = data.get("goal_id")

        if goal_id in (None, ""):
            return jsonify({"status": "error", "message": "Goal ID is required."}), 400

        user_id = config.get_current_user()["user_id"]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Goal deleted"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# --- CSV TOOLS (PROTECTED) ---

@expense_bp.route("/api/expense/upload", methods=["POST"])
def api_upload_csv():
    """
    Purpose: Handles CSV file processing and saves data to database.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"status": "error", "message": "Please choose a CSV file."}), 400

    try:
        user_id = config.get_current_user()["user_id"]

        import pandas as pd

        df = pd.read_csv(file)
        df.columns = [str(column).strip().lower() for column in df.columns]
        required_columns = {"amount", "category", "date"}
        if not required_columns.issubset(set(df.columns)):
            return jsonify({"status": "error", "message": "CSV must include amount, category, and date columns."}), 400

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

        conn = get_db_connection()
        cursor = conn.cursor()

        success_count = 0
        # Debug note: import one CSV row at a time so each line becomes one Expense record.
        for _, row in df.iterrows():
            amount = row.get("amount")
            category = row.get("category")
            date_str = row.get("date")
            description = "CSV Import"

            if pd.isna(amount) or pd.isna(date_str):
                continue

            try:
                amount_value = float(amount)
            except (TypeError, ValueError):
                continue

            if pd.isna(category) or category in (None, ""):
                category = "Other"

            cursor.execute(
                """
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, amount_value, category, date_str, description),
            )
            success_count += 1

        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "data": {"message": f"{success_count} rows successfully imported!"},
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error saving data: {str(e)}"}), 400


@expense_bp.route("/api/expense/export")
def api_export_data():
    """
    Purpose: Exports user expenses as a downloadable CSV.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, category, date FROM expenses WHERE user_id = ?", (user_id,))
        data = [dict(row) for row in cursor.fetchall()]
        conn.close()

        import pandas as pd

        df = pd.DataFrame(data)

        file_path = "static/expenses_export.csv"
        df.to_csv(file_path, index=False)

        return jsonify({"file": "/static/expenses_export.csv"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
