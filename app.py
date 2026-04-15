from flask import Flask, jsonify, render_template, request
import csv
import io

app = Flask(__name__)


# --- IN-MEMORY DEMO DATA ---

USERS = [
    {
        "id": "1",
        "username": "alex_coder",
        "email": "alex@example.com",
        "plan": "PRO",
        "joined_date": "2024-03-10",
    },
    {
        "id": "2",
        "username": "sarah_mkt",
        "email": "sarah@company.net",
        "plan": "FREE",
        "joined_date": "2024-04-01",
    },
]

EXPENSES = [
    {"description": "Starbucks", "amount": 4.5, "category": "Food", "date": "2024-04-14"},
    {"description": "AWS Bill", "amount": 120.0, "category": "Other", "date": "2024-04-12"},
]

GOALS = [
    {"name": "Modern Apartment", "target": 50000, "deadline": "", "saved": 16000},
    {"name": "Tesla Model S", "target": 90000, "deadline": "", "saved": 9000},
]

FEEDBACK_LOG = [
    {
        "subject": "Bug in Investment Chart",
        "message": "The 10-year projection doesn't seem to update when I change my SIP amount.",
        "email": "john.doe@test.com",
        "created_at": "Today, 10:45 AM",
    },
    {
        "subject": "Feature Request: Crypto Support",
        "message": "Would love to see Bitcoin and Ethereum tracking in the portfolio section.",
        "email": "crypto_fan@web3.io",
        "created_at": "Yesterday, 4:20 PM",
    },
]

REVIEWS = [
    {
        "id": "1",
        "name": "Sarah Chen",
        "rating": 5,
        "review": "The stability indicator is a lifesaver. I finally feel in control of my financial future.",
        "status": "APPROVED",
    },
    {
        "id": "2",
        "name": "Mike Ross",
        "rating": 4,
        "review": "Clean layout, but would love a dark mode toggle for the dash.",
        "status": "PENDING",
    },
]

MARKET_STATE = {"state": "stable"}
PROFILE = {"username": "Financial Explorer", "email": "user@smartvest.ai"}
INCOME = {"monthly": 5200.0}


def current_user():
    return {
        "username": PROFILE["username"],
        "email": PROFILE["email"],
    }


def json_success(**payload):
    return jsonify({"status": "success", **payload})


# --- TEMPLATE ROUTES ---

# Public Routes
@app.route("/")
def home():
    return render_template("public/home.html")


@app.route("/about")
def about():
    return render_template("public/about.html")


@app.route("/reviews")
def reviews_page():
    return render_template("public/reviews.html")


@app.route("/contact")
def contact():
    return render_template("public/contact.html")


@app.route("/login")
def login():
    return render_template("public/login.html")


@app.route("/signup")
def signup():
    return render_template("public/signup.html")


# User App Routes
@app.route("/dashboard")
def dashboard():
    return render_template("user/dashboard.html", active_page="dashboard", user=current_user())


@app.route("/expenses")
def expenses():
    return render_template("user/expense.html", active_page="expenses", user=current_user())


@app.route("/goals")
def goals():
    return render_template("user/goals.html", active_page="goals", user=current_user())


@app.route("/analysis")
def analysis():
    return render_template("user/analysis.html", active_page="analysis", user=current_user())


@app.route("/investment")
def investment():
    return render_template("user/investment.html", active_page="investment", user=current_user())


@app.route("/feedback")
def feedback():
    return render_template("user/feedback.html", active_page="feedback", user=current_user())


@app.route("/settings")
def settings():
    return render_template("user/settings.html", active_page="settings", user=current_user())


# Admin Routes
@app.route("/admin/dashboard")
def admin_dashboard():
    return render_template("admin/dashboard.html")


@app.route("/admin/users")
def admin_users():
    return render_template("admin/users.html")


@app.route("/admin/feedback")
def admin_feedback():
    return render_template("admin/feedback.html")


@app.route("/admin/reviews")
def admin_reviews():
    return render_template("admin/reviews.html")


@app.route("/admin/market")
def admin_market():
    return render_template("admin/dashboard.html")


# --- MOCK API ROUTES ---

@app.route("/api/dashboard")
def api_dashboard():
    total_expenses = sum(item["amount"] for item in EXPENSES)
    total_savings = max(INCOME["monthly"] * 3 - total_expenses, 0)
    return jsonify(
        {
            "total_expenses": round(total_expenses, 2),
            "total_savings": round(total_savings, 2),
            "goal_progress": 65,
            "username": PROFILE["username"],
        }
    )


@app.route("/api/expenses")
def api_expenses():
    return jsonify(EXPENSES)


@app.route("/api/add-expense", methods=["POST"])
def api_add_expense():
    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()
    category = (data.get("category") or "Other").strip() or "Other"
    amount = data.get("amount")

    if not description or amount in (None, ""):
        return jsonify({"message": "Description and amount are required."}), 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"message": "Amount must be numeric."}), 400

    EXPENSES.insert(
        0,
        {
            "description": description,
            "amount": amount,
            "category": category,
            "date": "2026-04-15",
        },
    )
    return json_success(expense=EXPENSES[0])


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    if not data.get("email") or not data.get("password"):
        return jsonify({"message": "Email and password are required."}), 400
    return json_success(user=current_user())


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or {}
    if not data.get("username") or not data.get("email") or not data.get("password"):
        return jsonify({"message": "All signup fields are required."}), 400

    PROFILE["username"] = data["username"].strip() or PROFILE["username"]
    PROFILE["email"] = data["email"].strip() or PROFILE["email"]
    return json_success(user=current_user())


@app.route("/api/logout", methods=["POST"])
def api_logout():
    return json_success(message="Logged out.")


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    subject = (data.get("subject") or "General Inquiry").strip()
    email = (data.get("email") or PROFILE["email"]).strip() or PROFILE["email"]

    if not message:
        return jsonify({"message": "Message is required."}), 400

    FEEDBACK_LOG.insert(
        0,
        {
            "subject": subject,
            "message": message,
            "email": email,
            "created_at": "Just now",
        },
    )
    return json_success(message="received")


@app.route("/api/review", methods=["POST"])
def api_review():
    data = request.get_json(silent=True) or {}
    review = (data.get("review") or "").strip()
    rating = int(data.get("rating") or 5)

    if not review:
        return jsonify({"message": "Review text is required."}), 400

    REVIEWS.insert(
        0,
        {
            "id": str(len(REVIEWS) + 1),
            "name": PROFILE["username"],
            "rating": max(1, min(rating, 5)),
            "review": review,
            "status": "PENDING",
        },
    )
    return json_success(review=REVIEWS[0])


@app.route("/api/reviews")
def api_reviews():
    return jsonify(REVIEWS)


@app.route("/api/set-income", methods=["POST"])
def api_set_income():
    data = request.get_json(silent=True) or {}
    amount = data.get("income")
    if amount in (None, ""):
        return jsonify({"message": "Income amount is required."}), 400

    try:
        INCOME["monthly"] = float(amount)
    except (TypeError, ValueError):
        return jsonify({"message": "Income must be numeric."}), 400

    return json_success(income=INCOME["monthly"])


@app.route("/api/expense-analysis")
def api_expense_analysis():
    total_expenses = sum(item["amount"] for item in EXPENSES)
    savings_rate = max(((INCOME["monthly"] - total_expenses) / max(INCOME["monthly"], 1)) * 100, 0)
    return jsonify(
        {
            "summary": f"You are saving approximately {savings_rate:.0f}% of monthly income.",
            "total_expenses": total_expenses,
            "income": INCOME["monthly"],
        }
    )


@app.route("/api/goal-status")
def api_goal_status():
    return jsonify(GOALS)


@app.route("/api/set-goal", methods=["POST"])
def api_set_goal():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    target = data.get("target")

    if not name or target in (None, ""):
        return jsonify({"message": "Goal name and target are required."}), 400

    try:
        target = float(target)
    except (TypeError, ValueError):
        return jsonify({"message": "Target must be numeric."}), 400

    GOALS.insert(
        0,
        {
            "name": name,
            "target": target,
            "deadline": data.get("deadline") or "",
            "saved": 0,
        },
    )
    return json_success(goal=GOALS[0])


@app.route("/api/investment")
def api_investment():
    return jsonify(
        {
            "market_state": MARKET_STATE["state"],
            "strategies": [
                {"title": "Fixed Deposit Plus", "risk": "Low", "return_rate": "7.5%"},
                {"title": "Automated SIP", "risk": "Moderate", "return_rate": "12-15%"},
                {"title": "Dynamic Stock Pick", "risk": "High", "return_rate": "Variable"},
            ],
        }
    )


@app.route("/api/update-profile", methods=["POST"])
def api_update_profile():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()

    if not username or not email:
        return jsonify({"message": "Username and email are required."}), 400

    PROFILE["username"] = username
    PROFILE["email"] = email
    return json_success(user=current_user())


@app.route("/api/change-password", methods=["POST"])
def api_change_password():
    data = request.get_json(silent=True) or {}
    if not data.get("current_password") or not data.get("new_password"):
        return jsonify({"message": "Both password fields are required."}), 400
    return json_success(message="Password updated.")


@app.route("/api/upload-csv", methods=["POST"])
def api_upload_csv():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"message": "Please choose a CSV file first."}), 400
    return json_success(message=f"{uploaded.filename} uploaded successfully.")


@app.route("/api/export-data")
def api_export_data():
    export_type = request.args.get("type") or "month"
    export_value = request.args.get("value") or ""

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["description", "category", "amount", "date"])
    for expense in EXPENSES:
        writer.writerow(
            [expense["description"], expense["category"], expense["amount"], expense["date"]]
        )

    filename = f"smartvest_export_{export_type or 'data'}.csv"
    return csv_buffer.getvalue(), 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": f"attachment; filename={filename}",
        "X-Export-Value": export_value,
    }


# --- ADMIN API ROUTES ---

@app.route("/api/admin/dashboard")
def api_admin_dashboard():
    return jsonify(
        {
            "users": len(USERS),
            "feedback_count": len(FEEDBACK_LOG),
            "reviews_count": len(REVIEWS),
            "market_state": MARKET_STATE["state"],
        }
    )


@app.route("/api/admin/users")
def api_admin_users():
    return jsonify(USERS)


@app.route("/api/admin/delete-user", methods=["DELETE"])
def api_admin_delete_user():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("userId") or "")
    remaining = [user for user in USERS if user["id"] != user_id]
    if len(remaining) == len(USERS):
        return jsonify({"message": "User not found."}), 404

    USERS.clear()
    USERS.extend(remaining)
    return json_success(message="User deleted.")


@app.route("/api/admin/market", methods=["POST"])
def api_admin_market():
    data = request.get_json(silent=True) or {}
    state = (data.get("state") or "").strip().lower()
    if state not in {"bullish", "stable", "bearish"}:
        return jsonify({"message": "Invalid market state."}), 400

    MARKET_STATE["state"] = state
    return json_success(state=state)


@app.route("/api/admin/feedback")
def api_admin_feedback():
    return jsonify(FEEDBACK_LOG)


@app.route("/api/admin/reviews")
def api_admin_reviews():
    return jsonify(REVIEWS)


if __name__ == "__main__":
    app.run(debug=True)
