"""
admin.py
--------
Purpose : Handles all admin-only pages and their data APIs.
          ALL data now comes directly from the SQLite database —
          no more config.USERS, config.FEEDBACK_LOG, or config.REVIEWS.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import config
from utils.db import get_db_connection   # ← real database helper
from modules.analysis import analyze_stock_rows, load_stock_csv

# Create the Admin Blueprint
admin_bp = Blueprint('admin', __name__)


# =============================================================================
# ADMIN UI PAGE ROUTES  (return HTML pages — admin-only)
# =============================================================================

@admin_bp.route("/admin/dashboard")
def admin_dashboard():
    """
    Purpose : Renders the central Admin Systems Console page.
    Input   : None
    Output  : HTML page, or redirect if not admin.
    """
    # If not even logged in, send to login page
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    # If logged in but not admin, send to user dashboard
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))

    return render_template("admin/dashboard.html")


@admin_bp.route("/admin/users")
def admin_users():
    """
    Purpose : Renders the User Management table page.
    Input   : None
    Output  : Admin-protected HTML page.
    """
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))

    return render_template("admin/users.html")


@admin_bp.route("/admin/feedback")
def admin_feedback_page():
    """
    Purpose : Renders the Feedback Log viewer page (admin only).
    Input   : None
    Output  : Admin-protected HTML page.
    """
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))

    return render_template("admin/feedback.html")


@admin_bp.route("/admin/reviews")
def admin_reviews_page():
    """
    Purpose : Renders the Review Moderation viewer page (admin only).
    Input   : None
    Output  : Admin-protected HTML page.
    """
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))

    return render_template("admin/reviews.html")


@admin_bp.route("/admin/market-metrics")
def admin_market_metrics_page():
    """
    Purpose : Renders the Market Metrics page for stock.csv analysis.
    Input   : None
    Output  : Admin-protected HTML page.
    """
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))

    return render_template("admin/market_metrics.html")


# =============================================================================
# ADMIN API ROUTES  (return JSON data — admin-only)
# =============================================================================

@admin_bp.route("/api/admin/stats")
def api_admin_stats():
    """
    Purpose : Aggregates system-wide metrics for the admin dashboard cards.
              Counts users, feedback entries, and reviews from the database.
    Input   : None  (admin session required)
    Output  : JSON with user count, feedback count, review count, market state.
    """
    # Only admins are allowed here
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    try:
        # Open database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Count total registered users (excluding the admin account itself)
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE role != 'admin'")
        user_count = cursor.fetchone()["total"]

        # Count total feedback messages submitted
        cursor.execute("SELECT COUNT(*) as total FROM feedback")
        feedback_count = cursor.fetchone()["total"]

        # Count total reviews submitted
        cursor.execute("SELECT COUNT(*) as total FROM reviews")
        review_count = cursor.fetchone()["total"]

        # Close the connection after reading all counts
        conn.close()

        # Return the stats as JSON for the admin dashboard
        return jsonify({
            "status": "success",
            "data": {
                "users":           user_count,
                "feedback_count":  feedback_count,
                "reviews_count":   review_count,
                "market_state":    config.MARKET_STATE["state"],
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/user/all")
def api_admin_users():
    """
    Purpose : Returns a list of all registered (non-admin) users from the database.
    Input   : None  (admin session required)
    Output  : JSON array of user objects.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        # Open database and fetch all non-admin users
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, email, role FROM users WHERE role != 'admin'"
        )
        # Convert each row into a plain dictionary so it can be turned into JSON
        all_users = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({"status": "success", "data": all_users})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/user/delete", methods=["DELETE"])
def api_admin_delete_user():
    """
    Purpose : Permanently removes a user from the database by their integer ID.
              Also removes all their expenses, goals, income, feedback, and reviews.
    Input   : JSON body with key "userId" (integer)
    Output  : Success message or error.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        # Read the JSON body sent by the frontend
        data = request.get_json(silent=True) or {}

        # Get the user ID as an integer — important for correct DB comparison
        user_id = data.get("userId")
        if user_id is None:
            return jsonify({"status": "error", "message": "userId is required."}), 400

        user_id = int(user_id)   # Make sure it is an integer, not a string

        # Open database
        conn = get_db_connection()
        cursor = conn.cursor()

        # First check if the user actually exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        found = cursor.fetchone()

        if found is None:
            conn.close()
            return jsonify({"status": "error", "message": "User not found."}), 404

        # Delete all related data first (foreign key cleanup)
        cursor.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM goals    WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM income   WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM reviews  WHERE user_id = ?", (user_id,))

        # Now delete the user record itself
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        # Save changes to the database
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "data": {"message": "User deleted successfully."}})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/market/update", methods=["POST"])
def api_admin_market():
    """
    Purpose : Updates the global market state variable (bullish / stable / bearish).
    Input   : JSON body with key "state" (string)
    Output  : Updated state value.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        state = (data.get("state") or "").strip().lower()

        # Only these three values are valid
        if state not in {"bullish", "stable", "bearish"}:
            return jsonify({"status": "error", "message": "Invalid state. Use: bullish, stable, or bearish."}), 400

        # Update the in-memory market state (this is kept in config as it is not user-specific)
        config.MARKET_STATE["state"] = state

        return jsonify({"status": "success", "data": {"state": state}})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/market-insight")
def api_admin_market_insight():
    """
    Purpose : Summarizes the stock market mix from data/stock.csv.
    Output  : JSON with Good / Bad / Stable counts and a short market status message.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        stocks = load_stock_csv()
        analyzed_stocks, status_counts = analyze_stock_rows(stocks, generate_charts=False)
        good_count = status_counts["Good"]
        bad_count = status_counts["Bad"]
        stable_count = status_counts["Stable"]
        total_count = len(analyzed_stocks)

        if total_count == 0:
            market_status = "No market data available"
        elif good_count > bad_count:
            market_status = "Market is performing well"
        else:
            market_status = "Market is unstable"

        return jsonify({
            "status": "success",
            "data": {
                "total": total_count,
                "good": good_count,
                "bad": bad_count,
                "stable": stable_count,
                "market_status": market_status,
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/feedback/all")
def api_admin_feedback():
    """
    Purpose : Retrieves all feedback messages from the database for admin review.
    Input   : None  (admin session required)
    Output  : JSON array of feedback objects.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        # Open database and join feedback with users table to get the username
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                feedback.id,
                feedback.user_id,
                users.username,
                feedback.message,
                feedback.subject,
                feedback.date
            FROM feedback
            LEFT JOIN users ON feedback.user_id = users.id
            ORDER BY feedback.id DESC
        """)

        # Convert rows to plain dictionaries for JSON serialisation
        all_feedback = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({"status": "success", "data": all_feedback})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/review/all")
def api_admin_reviews():
    """
    Purpose : Retrieves all user reviews from the database for admin moderation.
    Input   : None  (admin session required)
    Output  : JSON array of review objects.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        # Open database and join reviews with users table to get the username
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                reviews.id,
                reviews.user_id,
                users.username,
                reviews.rating,
                reviews.comment,
                reviews.status,
                reviews.date
            FROM reviews
            LEFT JOIN users ON reviews.user_id = users.id
            ORDER BY reviews.id DESC
        """)

        all_reviews = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({"status": "success", "data": all_reviews})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@admin_bp.route("/api/admin/review/delete", methods=["DELETE"])
def api_admin_delete_review():
    """
    Purpose : Deletes a user review from the database by review ID.
    Input   : JSON body with key "reviewId" (integer)
    Output  : Success message or error.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        review_id = data.get("reviewId")

        if review_id is None:
            return jsonify({"status": "error", "message": "reviewId is required."}), 400

        review_id = int(review_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM reviews WHERE id = ?", (review_id,))
        found = cursor.fetchone()

        if found is None:
            conn.close()
            return jsonify({"status": "error", "message": "Review not found."}), 404

        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "data": {"message": "Review deleted successfully."}})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
