"""Admin routes and APIs for SmartVest.

Big picture:
- render admin pages
- expose moderation and engagement data
- manage users, feedback, reviews, and uploaded market datasets
"""

from datetime import datetime, timedelta
import os

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

import config
from utils.api_errors import safe_api_error
from utils.db import get_db_connection
from utils.market_data import (
    save_uploaded_market_dataset,
    get_market_dataset_rows,
    get_active_dataset,
    get_dataset_preview,
    RETENTION_LIMIT,
)


admin_bp = Blueprint("admin", __name__)


# =============================================================================
# ADMIN UI PAGE ROUTES
# =============================================================================

@admin_bp.route("/admin/dashboard")
def admin_dashboard():
    """Render the platform monitoring dashboard."""
    if not config.is_logged_in():
        return redirect(url_for("auth.login"))
    if not config.is_admin():
        return redirect(url_for("analysis.dashboard"))
    return render_template("admin/dashboard.html")


@admin_bp.route("/admin/users")
def admin_users():
    """Render the user management page."""
    if not config.is_admin():
        return redirect(url_for("analysis.dashboard"))
    return render_template("admin/users.html")


@admin_bp.route("/admin/feedback")
def admin_feedback_page():
    """Render the feedback log page."""
    if not config.is_admin():
        return redirect(url_for("analysis.dashboard"))
    return render_template("admin/feedback.html")


@admin_bp.route("/admin/reviews")
def admin_reviews_page():
    """Render the review moderation page."""
    if not config.is_admin():
        return redirect(url_for("analysis.dashboard"))
    return render_template("admin/reviews.html")


@admin_bp.route("/admin/market-metrics")
def admin_market_metrics_page():
    """Render the existing market metrics page."""
    if not config.is_admin():
        return redirect(url_for("analysis.dashboard"))
    return render_template("admin/market_metrics.html")


@admin_bp.route("/admin/market-datasets")
def admin_market_datasets_page():
    """Render the market dataset manager page."""
    if not config.is_admin():
        return redirect(url_for("analysis.dashboard"))
    return render_template("admin/market_datasets.html")


# =============================================================================
# DASHBOARD HELPERS
# =============================================================================

def _admin_required():
    """Keep admin-only API checks readable and consistent."""
    return config.is_admin()


def _count(cursor, query, params=()):
    cursor.execute(query, params)
    row = cursor.fetchone()
    return row[0] if row else 0


def _feedback_base_select():
    return """
        SELECT
            feedback.id,
            feedback.user_id,
            users.username,
            feedback.subject,
            feedback.message,
            feedback.date,
            feedback.status,
            feedback.accepted_at,
            feedback.resolved
        FROM feedback
        LEFT JOIN users ON feedback.user_id = users.id
    """


def _feedback_exists(cursor, feedback_id):
    cursor.execute("SELECT id FROM feedback WHERE id = ?", (feedback_id,))
    return cursor.fetchone() is not None


def _review_base_select():
    return """
        SELECT
            reviews.id,
            reviews.user_id,
            users.username,
            reviews.rating,
            reviews.comment,
            reviews.status,
            reviews.date,
            reviews.show_public,
            reviews.approved_at
        FROM reviews
        LEFT JOIN users ON reviews.user_id = users.id
    """


def _review_exists(cursor, review_id):
    cursor.execute("SELECT id FROM reviews WHERE id = ?", (review_id,))
    return cursor.fetchone() is not None


def _activity_union_sql():
    return """
        SELECT user_id, date, 'Expenses' AS module FROM expenses WHERE user_id IS NOT NULL
        UNION ALL
        SELECT user_id, date, 'Income' AS module FROM income WHERE user_id IS NOT NULL
        UNION ALL
        SELECT user_id, date, 'Feedback' AS module FROM feedback WHERE user_id IS NOT NULL
        UNION ALL
        SELECT user_id, date, 'Reviews' AS module FROM reviews WHERE user_id IS NOT NULL
    """


def _date_labels(days=7):
    today = datetime.now().date()
    return [(today - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days - 1, -1, -1)]


def _activity_counts(cursor):
    total_users = _count(cursor, "SELECT COUNT(*) FROM users WHERE role != 'admin'")
    active_users = _count(cursor, f"""
        SELECT COUNT(DISTINCT user_id)
        FROM ({_activity_union_sql()})
        WHERE date >= date('now', '-30 day')
    """)
    return total_users, active_users, max(total_users - active_users, 0)


# =============================================================================
# DASHBOARD API ROUTES
# =============================================================================

@admin_bp.route("/api/admin/activity-stats")
def api_admin_activity_stats():
    """Return top-card platform counts."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        total_users, active_users, inactive_users = _activity_counts(cursor)
        feedback_count = _count(cursor, "SELECT COUNT(*) FROM feedback")
        review_count = _count(cursor, "SELECT COUNT(*) FROM reviews")
        new_users_week = _count(cursor, """
            SELECT COUNT(*)
            FROM users
            WHERE role != 'admin' AND created_at >= date('now', '-6 day')
        """)
        conn.close()

        return jsonify({
            "status": "success",
            "data": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": inactive_users,
                "new_users_week": new_users_week,
                "feedback_count": feedback_count,
                "review_count": review_count,
                "users": total_users,
                "reviews_count": review_count,
            },
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/engagement-metrics")
def api_admin_engagement_metrics():
    """Return chart data and short platform insights."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        labels = _date_labels()
        conn = get_db_connection()
        cursor = conn.cursor()
        total_users, active_users, inactive_users = _activity_counts(cursor)

        current_week = _count(cursor, f"""
            SELECT COUNT(*) FROM ({_activity_union_sql()})
            WHERE date >= date('now', '-6 day')
        """)
        previous_week = _count(cursor, f"""
            SELECT COUNT(*) FROM ({_activity_union_sql()})
            WHERE date BETWEEN date('now', '-13 day') AND date('now', '-7 day')
        """)
        cursor.execute(f"""
            SELECT date, COUNT(*) AS total
            FROM ({_activity_union_sql()})
            WHERE date >= ?
            GROUP BY date
        """, (labels[0],))
        trend_counts = {row["date"]: row["total"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT module, total FROM (
                SELECT 'Expenses' AS module, COUNT(*) AS total FROM expenses
                UNION ALL SELECT 'Income', COUNT(*) FROM income
                UNION ALL SELECT 'Goals', COUNT(*) FROM goals
                UNION ALL SELECT 'Feedback', COUNT(*) FROM feedback
                UNION ALL SELECT 'Reviews', COUNT(*) FROM reviews
            )
            ORDER BY total DESC
            LIMIT 1
        """)
        top_module = cursor.fetchone()
        conn.close()

        engagement_percent = round((active_users / total_users) * 100, 1) if total_users else 0
        top_module_name = top_module["module"] if top_module and top_module["total"] else "No activity yet"
        activity_direction = "increased" if current_week >= previous_week else "decreased"

        return jsonify({
            "status": "success",
            "data": {
                "active_users": active_users,
                "inactive_users": inactive_users,
                "engagement_percent": engagement_percent,
                "weekly_trend": {
                    "labels": labels,
                    "values": [trend_counts.get(label, 0) for label in labels],
                },
                "active_split": {
                    "labels": ["Active", "Inactive"],
                    "values": [active_users, inactive_users],
                },
                "most_active_module": top_module_name,
                "insights": [
                    f"Activity {activity_direction} compared with the previous week.",
                    "Inactive users are rising." if inactive_users > active_users else "Active users are leading engagement.",
                    f"Most active module: {top_module_name}.",
                ],
            },
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/reminders")
def api_admin_reminders():
    """Return moderation and admin action reminders."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        pending_reviews = _count(cursor, "SELECT COUNT(*) FROM reviews WHERE UPPER(COALESCE(status, 'PENDING')) = 'PENDING'")
        new_feedback = _count(cursor, "SELECT COUNT(*) FROM feedback WHERE date >= date('now', '-6 day')")
        conn.close()

        return jsonify({
            "status": "success",
            "data": {
                "pending_reviews": pending_reviews,
                "new_feedback": new_feedback,
                "unresolved_admin_actions": pending_reviews + new_feedback,
            },
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/recent-activity")
def api_admin_recent_activity():
    """Return recent signups, reviews, and feedback."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, email, created_at
            FROM users
            WHERE role != 'admin'
            ORDER BY COALESCE(created_at, '') DESC, id DESC
            LIMIT 5
        """)
        signups = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT reviews.id, users.username, reviews.rating, reviews.comment, reviews.status, reviews.date
            FROM reviews
            LEFT JOIN users ON reviews.user_id = users.id
            ORDER BY reviews.id DESC
            LIMIT 5
        """)
        reviews = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT feedback.id, users.username, feedback.subject, feedback.message, feedback.date
            FROM feedback
            LEFT JOIN users ON feedback.user_id = users.id
            ORDER BY feedback.id DESC
            LIMIT 5
        """)
        feedback = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            "status": "success",
            "data": {
                "signups": signups,
                "reviews": reviews,
                "feedback": feedback,
            },
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)


# =============================================================================
# EXISTING ADMIN DATA API ROUTES
# =============================================================================

@admin_bp.route("/api/admin/user/all")
def api_admin_users():
    """Return all non-admin users."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, role FROM users WHERE role != 'admin'")
        all_users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": all_users})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/user/delete", methods=["DELETE"])
def api_admin_delete_user():
    """Delete a user and their related platform records."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get("userId")
        if user_id is None:
            return jsonify({"status": "error", "message": "userId is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = ?", (int(user_id),))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"status": "error", "message": "User not found."}), 404

        for table in ("expenses", "goals", "income", "feedback", "reviews"):
            cursor.execute(f"DELETE FROM {table} WHERE user_id = ?", (int(user_id),))
        cursor.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "User deleted successfully."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/feedback/all")
def api_admin_feedback():
    """Return all feedback messages."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            {_feedback_base_select()}
            ORDER BY feedback.id DESC
        """)
        all_feedback = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": all_feedback})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/feedback/incoming")
def api_admin_feedback_incoming():
    """Return pending incoming feedback for moderation."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            {_feedback_base_select()}
            WHERE LOWER(COALESCE(feedback.status, 'pending')) = 'pending'
            ORDER BY feedback.id DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": rows})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/feedback/accepted")
def api_admin_feedback_accepted():
    """Return accepted feedback with resolution status."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            {_feedback_base_select()}
            WHERE LOWER(COALESCE(feedback.status, 'pending')) = 'accepted'
            ORDER BY COALESCE(feedback.accepted_at, feedback.date) DESC, feedback.id DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": rows})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/feedback/accept", methods=["POST"])
def api_admin_feedback_accept():
    """Mark feedback as accepted and initialize unresolved workflow."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        feedback_id = data.get("feedbackId")
        if feedback_id is None:
            return jsonify({"status": "error", "message": "feedbackId is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        feedback_id = int(feedback_id)
        if not _feedback_exists(cursor, feedback_id):
            conn.close()
            return jsonify({"status": "error", "message": "Feedback not found."}), 404

        cursor.execute("""
            UPDATE feedback
            SET status = 'accepted',
                accepted_at = ?,
                resolved = 0
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), feedback_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "Feedback accepted."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/feedback/delete", methods=["DELETE"])
def api_admin_feedback_delete():
    """Permanently delete a feedback entry."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        feedback_id = data.get("feedbackId")
        if feedback_id is None:
            return jsonify({"status": "error", "message": "feedbackId is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        feedback_id = int(feedback_id)
        if not _feedback_exists(cursor, feedback_id):
            conn.close()
            return jsonify({"status": "error", "message": "Feedback not found."}), 404

        cursor.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "Feedback deleted."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/feedback/resolve", methods=["POST"])
def api_admin_feedback_resolve():
    """Mark accepted feedback as resolved."""
    return _set_feedback_resolved_value(1)


@admin_bp.route("/api/admin/feedback/unresolve", methods=["POST"])
def api_admin_feedback_unresolve():
    """Mark accepted feedback as not resolved."""
    return _set_feedback_resolved_value(0)


def _set_feedback_resolved_value(value):
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        feedback_id = data.get("feedbackId")
        if feedback_id is None:
            return jsonify({"status": "error", "message": "feedbackId is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        feedback_id = int(feedback_id)
        if not _feedback_exists(cursor, feedback_id):
            conn.close()
            return jsonify({"status": "error", "message": "Feedback not found."}), 404

        cursor.execute("SELECT LOWER(COALESCE(status, 'pending')) AS status FROM feedback WHERE id = ?", (feedback_id,))
        row = cursor.fetchone()
        if row is None or row["status"] != "accepted":
            conn.close()
            return jsonify({"status": "error", "message": "Only accepted feedback can be updated."}), 400

        cursor.execute("UPDATE feedback SET resolved = ? WHERE id = ?", (value, feedback_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "Feedback resolution updated."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/market-dataset/list")
def api_admin_market_dataset_list():
    """Return latest dataset rows and active dataset info."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        rows = get_market_dataset_rows(limit=RETENTION_LIMIT)
        return jsonify({
            "status": "success",
            "data": {
                "datasets": rows,
                "active": get_active_dataset(),
            },
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/market-dataset/upload", methods=["POST"])
def api_admin_market_dataset_upload():
    """Upload a CSV dataset and make it active."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        upload_file = request.files.get("file")
        if upload_file is None or not upload_file.filename:
            return jsonify({"status": "error", "message": "CSV file is required."}), 400

        allowed_mimes = {
            "text/csv",
            "application/csv",
            "application/vnd.ms-excel",
            "text/plain",
            "application/octet-stream",
        }
        if not upload_file.filename.lower().endswith(".csv") or upload_file.mimetype not in allowed_mimes:
            return jsonify({"status": "error", "message": "Please upload a valid CSV file."}), 400

        upload_file.stream.seek(0, os.SEEK_END)
        file_size = upload_file.stream.tell()
        upload_file.stream.seek(0)
        if file_size > 16 * 1024 * 1024:
            return jsonify({"status": "error", "message": "CSV file is too large."}), 413

        saved = save_uploaded_market_dataset(upload_file)
        preview = get_dataset_preview(saved["dataset_path"], limit=8)
        return jsonify({
            "status": "success",
            "data": {
                "dataset": saved,
                "preview": preview,
                "message": "Dataset uploaded and activated.",
            },
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": "Something went wrong. Please try again."}), 400
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/market-dataset/preview")
def api_admin_market_dataset_preview():
    """Preview active dataset rows."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        active = get_active_dataset()
        if not active:
            return jsonify({"status": "success", "data": {"preview": [], "active": None}})

        preview = get_dataset_preview(active["dataset_path"], limit=8)
        return jsonify({"status": "success", "data": {"preview": preview, "active": active}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/review/all")
def api_admin_reviews():
    """Return all user reviews."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            {_review_base_select()}
            ORDER BY reviews.id DESC
        """)
        all_reviews = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": all_reviews})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/review/incoming")
def api_admin_reviews_incoming():
    """Return pending incoming reviews."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            {_review_base_select()}
            WHERE LOWER(COALESCE(reviews.status, 'pending')) = 'pending'
            ORDER BY reviews.id DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": rows})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/review/accepted")
def api_admin_reviews_accepted():
    """Return accepted reviews."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            {_review_base_select()}
            WHERE LOWER(COALESCE(reviews.status, 'pending')) = 'accepted'
            ORDER BY COALESCE(reviews.approved_at, reviews.date) DESC, reviews.id DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": rows})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/review/accept", methods=["POST"])
def api_admin_review_accept():
    """Accept a pending review and move it into accepted workflow."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        review_id = data.get("reviewId")
        if review_id is None:
            return jsonify({"status": "error", "message": "reviewId is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        review_id = int(review_id)
        if not _review_exists(cursor, review_id):
            conn.close()
            return jsonify({"status": "error", "message": "Review not found."}), 404

        cursor.execute("""
            UPDATE reviews
            SET status = 'accepted',
                approved_at = ?
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), review_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "Review accepted."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/review/public-toggle", methods=["POST"])
def api_admin_review_public_toggle():
    """
    Toggle review visibility on the public reviews page.
    Limit is 6 public reviews at a time.
    """
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        review_id = data.get("reviewId")
        show_public = int(data.get("showPublic", 0))

        if review_id is None:
            return jsonify({"status": "error", "message": "reviewId is required."}), 400
        if show_public not in (0, 1):
            return jsonify({"status": "error", "message": "showPublic must be 0 or 1."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        review_id = int(review_id)
        if not _review_exists(cursor, review_id):
            conn.close()
            return jsonify({"status": "error", "message": "Review not found."}), 404

        cursor.execute("SELECT LOWER(COALESCE(status, 'pending')) AS status FROM reviews WHERE id = ?", (review_id,))
        status_row = cursor.fetchone()
        if status_row is None or status_row["status"] != "accepted":
            conn.close()
            return jsonify({"status": "error", "message": "Only accepted reviews can be shown publicly."}), 400

        if show_public == 1:
            public_count = _count(cursor, "SELECT COUNT(*) FROM reviews WHERE show_public = 1")
            if public_count >= 6:
                conn.close()
                return jsonify({"status": "error", "message": "Public review limit reached (max 6)."}), 400

        cursor.execute("UPDATE reviews SET show_public = ? WHERE id = ?", (show_public, review_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "Public visibility updated."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/public/reviews")
def api_public_reviews():
    """Return up to 6 accepted reviews selected for the public page."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT users.username, reviews.rating, reviews.comment, reviews.date
            FROM reviews
            LEFT JOIN users ON reviews.user_id = users.id
            WHERE reviews.show_public = 1 AND LOWER(COALESCE(reviews.status, 'pending')) = 'accepted'
            ORDER BY COALESCE(reviews.approved_at, reviews.date) DESC, reviews.id DESC
            LIMIT 6
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "data": rows})
    except Exception as e:
        return safe_api_error(e, status_code=400)


@admin_bp.route("/api/admin/review/delete", methods=["DELETE"])
def api_admin_delete_review():
    """Delete a review by ID."""
    if not _admin_required():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        review_id = data.get("reviewId")
        if review_id is None:
            return jsonify({"status": "error", "message": "reviewId is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM reviews WHERE id = ?", (int(review_id),))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"status": "error", "message": "Review not found."}), 404

        cursor.execute("DELETE FROM reviews WHERE id = ?", (int(review_id),))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "data": {"message": "Review deleted successfully."}})
    except Exception as e:
        return safe_api_error(e, status_code=400)


