"""
analysis.py
-----------
Purpose : Handles the Dashboard and Analysis pages + their data APIs.
          ALL financial data now comes from the SQLite database — no more config lists.
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for
import config
from utils.db import get_db_connection   # ← real database helper
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.style.use("dark_background")

# Create the Analysis Blueprint so Flask can register these routes
analysis_bp = Blueprint('analysis', __name__)

STOCK_DAY_COLUMNS = [f"day{i}" for i in range(1, 11)]


def _coerce_float(value, default=0.0):
    """Convert a value to float safely, falling back to default on bad input."""
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _sum_numeric(rows, key):
    """Sum a numeric key from SQLite rows without crashing on null values."""
    total = 0.0
    for row in rows:
        total += _coerce_float(row[key])
    return total


def _safe_stock_name(name):
    """Convert a stock name into a filename-friendly value."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name))
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "stock"


def load_stock_csv():
    """
    Purpose : Load stock data from the CSV file used by the upgrade.
    Output  : Pandas DataFrame with the expected stock columns.
    """
    required_columns = ["name"] + STOCK_DAY_COLUMNS
    try:
        stocks = pd.read_csv("data/stock.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=required_columns)

    if "name" not in stocks.columns:
        stocks["name"] = ""

    for column in STOCK_DAY_COLUMNS:
        if column not in stocks.columns:
            stocks[column] = pd.NA

    return stocks.reindex(columns=required_columns)


def analyze_stock_rows(stocks, generate_charts=True):
    """
    Purpose : Classify each stock row and optionally generate a chart image.
    Input   : DataFrame with stock prices across day1..day10.
    Output  : (analysis list, status counts dictionary)
    """
    analyzed_stocks = []
    status_counts = {"Good": 0, "Bad": 0, "Stable": 0}

    if generate_charts:
        os.makedirs("static", exist_ok=True)

    for index, row in stocks.iterrows():
        stock_name = str(row["name"]).strip() or f"Stock {index + 1}"
        prices = [ _coerce_float(row[column]) for column in STOCK_DAY_COLUMNS ]
        change = float(prices[-1] - prices[0]) if prices else 0.0

        if change > 5:
            status = "Good"
        elif change < -5:
            status = "Bad"
        else:
            status = "Stable"

        status_counts[status] = status_counts[status] + 1

        chart_path = ""
        if generate_charts:
            safe_name = _safe_stock_name(stock_name)
            file_name = f"{safe_name}_stock.png"
            file_path = os.path.join("static", file_name)

            days = [f"Day {i}" for i in range(1, len(prices) + 1)]
            plt.figure(figsize=(6, 3.5))
            plt.plot(days, prices, marker="o", linewidth=2, color="#00c2ff")
            plt.title(f"{stock_name} Stock Trend", color="white")
            plt.xlabel("Day", color="white")
            plt.ylabel("Price", color="white")
            plt.xticks(rotation=25, color="white")
            plt.yticks(color="white")
            plt.grid(alpha=0.2)
            plt.tight_layout()
            plt.savefig(file_path, facecolor="black")
            plt.close()
            chart_path = "/static/" + file_name

        analyzed_stocks.append({
            "name": stock_name,
            "status": status,
            "change": round(change, 2),
            "prices": [float(price) for price in prices],
            "chart": chart_path,
        })

    return analyzed_stocks, status_counts


def get_risk_level(savings_rate):
    """Map savings rate to a beginner-friendly risk label."""
    if savings_rate < 20:
        return "Low"
    if savings_rate < 40:
        return "Medium"
    return "High"


def filter_recommended_stocks(stocks, risk_level):
    """Filter analyzed stocks by the chosen risk level."""
    allowed_status = {
        "Low": {"Stable"},
        "Medium": {"Stable", "Good"},
        "High": {"Good"},
    }.get(risk_level, {"Stable"})

    return [stock for stock in stocks if stock["status"] in allowed_status]


def classify_market_stock(percent_change):
    """
    Purpose : Classify a stock using percentage movement.
    Input   : percent_change as a float.
    Output  : Good, Bad, or Stable.
    """
    if percent_change > 5:
        return "Good"
    if percent_change < -5:
        return "Bad"
    return "Stable"


def _save_empty_chart(file_path, title, message):
    """Create a simple placeholder chart when no stock data is available."""
    plt.figure(figsize=(8, 4))
    plt.title(title, color="white")
    plt.text(0.5, 0.5, message, ha="center", va="center", color="white", fontsize=14)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(file_path, facecolor="black")
    plt.close()


def build_market_metrics():
    """
    Purpose : Analyze data/stock.csv and build admin market metrics.
    Output  : Dictionary with counts, market status, top movers, and chart paths.
    """
    stock_frame = load_stock_csv()
    os.makedirs("static", exist_ok=True)

    stock_rows = []
    good_count = 0
    bad_count = 0
    stable_count = 0

    if not stock_frame.empty:
        for index, row in stock_frame.iterrows():
            stock_name = str(row["name"]).strip() or f"Stock {index + 1}"
            day1 = pd.to_numeric(row["day1"], errors="coerce")
            day10 = pd.to_numeric(row["day10"], errors="coerce")

            day1_value = float(day1) if pd.notna(day1) else 0.0
            day10_value = float(day10) if pd.notna(day10) else 0.0

            if day1_value != 0:
                percent_change = ((day10_value - day1_value) / day1_value) * 100
            else:
                percent_change = 0.0

            status = classify_market_stock(percent_change)
            if status == "Good":
                good_count += 1
            elif status == "Bad":
                bad_count += 1
            else:
                stable_count += 1

            stock_rows.append({
                "name": stock_name,
                "day1": round(day1_value, 2),
                "day10": round(day10_value, 2),
                "percent_change": round(percent_change, 2),
                "status": status,
            })

    total_count = len(stock_rows)
    if total_count == 0:
        market_status = "No market data available"
    elif good_count > bad_count:
        market_status = "Growth"
    elif bad_count > good_count:
        market_status = "Down"
    else:
        market_status = "Stable"

    top_gainers = sorted(stock_rows, key=lambda item: item["percent_change"], reverse=True)[:5]
    top_losers = sorted(stock_rows, key=lambda item: item["percent_change"])[:5]

    trend_chart_path = "static/market_trend.png"
    summary_chart_path = "static/market_summary.png"

    if not stock_frame.empty:
        day_columns = [f"day{i}" for i in range(1, 11)]
        daily_average = stock_frame[day_columns].apply(pd.to_numeric, errors="coerce").fillna(0).mean(axis=0)
        x_values = list(range(1, 11))

        plt.figure(figsize=(9, 4.5))
        plt.plot(x_values, daily_average.values, marker="o", linewidth=2, color="#00c2ff")
        plt.title("Market Trend", color="white")
        plt.xlabel("Day", color="white")
        plt.ylabel("Average Price", color="white")
        plt.xticks(x_values, [f"Day {i}" for i in x_values], rotation=20, color="white")
        plt.yticks(color="white")
        plt.grid(alpha=0.2)
        plt.tight_layout()
        plt.savefig(trend_chart_path, facecolor="black")
        plt.close()
    else:
        _save_empty_chart(trend_chart_path, "Market Trend", "No stock data available")

    plt.figure(figsize=(7, 4.5))
    plt.bar(["Good", "Bad", "Stable"], [good_count, bad_count, stable_count], color=["#4ade80", "#f87171", "#a1a1aa"])
    plt.title("Market Summary", color="white")
    plt.xlabel("Classification", color="white")
    plt.ylabel("Count", color="white")
    plt.xticks(color="white")
    plt.yticks(color="white")
    plt.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(summary_chart_path, facecolor="black")
    plt.close()

    summary = (
        f"Analysed {total_count} stocks from data/stock.csv. "
        f"Good: {good_count}, Bad: {bad_count}, Stable: {stable_count}."
    )

    return {
        "summary": summary,
        "market_status": market_status,
        "counts": {
            "good": good_count,
            "bad": bad_count,
            "stable": stable_count,
            "total": total_count,
        },
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "charts": {
            "trend": "/static/market_trend.png",
            "summary": "/static/market_summary.png",
        },
    }


def get_user_financial_snapshot(user_id):
    """
    Purpose : Calculate the current user's income, expenses, savings and risk level.
    Output  : Dictionary used by investment-related APIs.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount FROM expenses WHERE user_id = ?",
        (user_id,)
    )
    expense_rows = cursor.fetchall()

    total_expenses = _sum_numeric(expense_rows, "amount")

    cursor.execute(
        "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    income_row = cursor.fetchone()
    monthly_income = _coerce_float(income_row["amount"]) if income_row is not None else 0.0

    conn.close()

    savings = monthly_income - total_expenses

    if monthly_income > 0:
        savings_rate = ((monthly_income - total_expenses) / monthly_income) * 100
    else:
        savings_rate = 0.0

    risk_level = get_risk_level(savings_rate)

    if savings <= 0:
        suggestion = "You have no savings. Focus on reducing expenses."
    elif savings_rate < 20:
        suggestion = "Your savings are low. Build an emergency fund first."
    elif savings_rate < 40:
        suggestion = "You can start investing in mutual funds or SIP."
    else:
        suggestion = "You have strong savings. Consider stocks and diversified investments."

    return {
        "total_expenses": round(total_expenses, 2),
        "income": round(monthly_income, 2),
        "savings": round(savings, 2),
        "savings_rate": round(savings_rate, 2),
        "risk_level": risk_level,
        "investment_suggestion": suggestion,
    }



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
        total_expenses = _sum_numeric(expense_rows, "amount")

        # Step 6: Fetch this user's monthly income (most recent record)
        cursor.execute(
            "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        income_row = cursor.fetchone()

        # Step 7: If no income record found, treat income as 0
        monthly_income = _coerce_float(income_row["amount"]) if income_row is not None else 0.0

        # Fetch goals from database using user_id
        cursor.execute(
            "SELECT target_amount, saved_amount FROM goals WHERE user_id = ?",
            (user_id,)
        )
        goal_rows = cursor.fetchall()
        
        # Add up all targets and saved amounts
        total_target = _sum_numeric(goal_rows, "target_amount")
        total_saved = _sum_numeric(goal_rows, "saved_amount")

        # Step 8: Close the database — we are done reading
        conn.close()

        # Step 9: Calculate savings exactly as income minus expenses.
        total_savings = monthly_income - total_expenses

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


@analysis_bp.route("/api/dashboard")
def api_dashboard_alias():
    """Compatibility alias for older clients expecting /api/dashboard."""
    return api_dashboard_data()


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
        total_expenses = _sum_numeric(expense_rows, "amount")

        # Step 6: Fetch the user's most recent monthly income
        cursor.execute(
            "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        income_row = cursor.fetchone()

        # Step 7: Default income to 0 when no data exists
        monthly_income = _coerce_float(income_row["amount"]) if income_row is not None else 0.0

        # Step 8: Close the database connection
        conn.close()

        # Step 9: Calculate savings rate as a percentage
        # Formula: savings_rate = ((income - expenses) / income) * 100
        if monthly_income > 0:
            savings_rate = ((monthly_income - total_expenses) / monthly_income) * 100
        else:
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


@analysis_bp.route("/api/analysis")
def api_analysis_alias():
    """Compatibility alias for older clients expecting /api/analysis."""
    return api_expense_analysis()


# =============================================================================
# DATA ANALYSIS ROUTES (Pandas Integration)
# =============================================================================

@analysis_bp.route("/api/analysis/dataframe")
def api_expenses_dataframe():
    """
    Purpose : Convert expense data from SQLite into a pandas DataFrame.
    Input   : user_id from the current session.
    Output  : JSON response confirming the DataFrame was successfully created.
    """
    # 1. Get user_id from current session
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        user_id = config.get_current_user()["user_id"]

        # 2. Fetch expenses from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT amount, category, date FROM expenses WHERE user_id = ?",
            (user_id,)
        )
        expense_rows = cursor.fetchall()

        # 2. Fetch income from database using user_id
        cursor.execute(
            "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        income_row = cursor.fetchone()
        income = float(income_row["amount"]) if income_row else 0.0

        conn.close()

        # 3. Store data as list of dictionaries
        expenses_list = []
        for row in expense_rows:
            expenses_list.append({
                "amount": row["amount"],
                "category": row["category"],
                "date": row["date"]
            })

        # 4. Convert to pandas DataFrame
        df = pd.DataFrame(expenses_list)

        if not df.empty:
            df = df.sort_values(by="date", ascending=False)

        # Purpose: Add financial metrics calculation
        # Input: pandas total_expense and database fetched income
        # Output: JSON with total_expense, income, savings, and savings_rate
        
        # 1. Use existing total_expense from pandas
        if not df.empty:
            total_expense = float(df["amount"].sum())
        else:
            total_expense = 0.0

        # 3. Calculate: savings = income - total_expense
        savings = income - total_expense

        # 4. Calculate savings rate:
        if income > 0:
            savings_rate = (savings / income) * 100
        else:
            savings_rate = 0.0

        # Purpose: Generate simple smart insights
        # Input: pandas DataFrame and savings_rate
        # Output: JSON response with insights messages appended

        # 1. Find highest spending category
        if not df.empty:
            top_category = df.groupby("category")["amount"].sum().idxmax()
        else:
            top_category = "None"

        # 2. Create savings insight
        if savings_rate < 20:
            savings_msg = "Your savings are low. Try to reduce expenses."
        elif savings_rate < 40:
            savings_msg = "Your savings are moderate."
        else:
            savings_msg = "Great job! You are saving well."

        # 3. Create spending insight
        if not df.empty:
            spending_msg = "You spend most on " + str(top_category)
        else:
            spending_msg = "You have no expenses yet."

        # Purpose: Generate investment suggestion and risk profile
        # Input: savings, savings_rate
        # Output: suggestion string and risk level label
        if savings <= 0:
            suggestion = "You have no savings. Focus on reducing expenses."
        elif savings_rate < 20:
            suggestion = "Your savings are low. Build an emergency fund first."
        elif savings_rate < 40:
            suggestion = "You can start investing in mutual funds or SIP."
        else:
            suggestion = "You have strong savings. Consider stocks and diversified investments."

        risk_level = get_risk_level(savings_rate)

        # Load stock CSV data and build stock analysis results
        stock_analysis = []
        stock_counts = {"Good": 0, "Bad": 0, "Stable": 0}
        stock_error = ""

        try:
            stock_frame = load_stock_csv()
            stock_analysis, stock_counts = analyze_stock_rows(stock_frame, generate_charts=True)
        except Exception as stock_exception:
            stock_error = str(stock_exception)

        recommended_stocks = filter_recommended_stocks(stock_analysis, risk_level)

        # Purpose: Generate matplotlib charts
        # Input: existing df
        # Output: paths to saved static images

        bar_chart_path = ""
        pie_chart_path = ""
        line_chart_path = ""

        if not df.empty:
            # Category Data
            category_data = df.groupby("category")["amount"].sum()

            # 3. Bar Chart (colorful)
            plt.figure(figsize=(7,4))
            category_data.plot(
                kind="bar",
                color=["#00c2ff", "#ff7b00", "#00ff9d", "#ff4d6d", "#ffd60a"]
            )
            plt.title("Category Spending", color="white")
            plt.xlabel("Category", color="white")
            plt.ylabel("Amount", color="white")
            plt.xticks(rotation=30)
            plt.tight_layout()
            plt.savefig("static/bar_chart.png")
            plt.close()
            bar_chart_path = "/static/bar_chart.png"

            # 4. Pie Chart (colorful)
            plt.figure(figsize=(5,5))
            category_data.plot(
                kind="pie",
                autopct="%1.1f%%",
                colors=["#00c2ff", "#ff7b00", "#00ff9d", "#ff4d6d", "#ffd60a"]
            )
            plt.title("Expense Distribution", color="white")
            plt.ylabel("")  # remove default label
            plt.tight_layout()
            plt.savefig("static/pie_chart.png")
            plt.close()
            pie_chart_path = "/static/pie_chart.png"

            # 5. Line Chart (trend)
            df["date"] = pd.to_datetime(df["date"])
            date_data = df.groupby("date")["amount"].sum()

            plt.figure(figsize=(7,4))
            date_data.plot(kind="line", marker="o", color="#00c2ff")
            plt.title("Spending Over Time", color="white")
            plt.xlabel("Date", color="white")
            plt.ylabel("Amount", color="white")
            plt.xticks(rotation=30)
            plt.grid(alpha=0.2)
            plt.tight_layout()
            plt.savefig("static/line_chart.png")
            plt.close()
            line_chart_path = "/static/line_chart.png"

        return jsonify({
            "total_expense": total_expense,
            "income": income,
            "savings": savings,
            "savings_rate": savings_rate,
            "risk_level": risk_level,
            "top_category": top_category,
            "savings_message": savings_msg,
            "spending_message": spending_msg,
            "investment_suggestion": suggestion,
            "stock_summary": {
                "total": len(stock_analysis),
                "good": stock_counts["Good"],
                "bad": stock_counts["Bad"],
                "stable": stock_counts["Stable"],
            },
            "stocks": stock_analysis,
            "recommended_stocks": recommended_stocks,
            "stock_error": stock_error,
            "bar_chart": bar_chart_path,
            "pie_chart": pie_chart_path,
            "line_chart": line_chart_path
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
