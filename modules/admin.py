from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import config

# Create the Admin Blueprint
admin_bp = Blueprint('admin', __name__)

# --- ADMIN UI PAGE ROUTES (STRICT PROTECTED) ---

@admin_bp.route("/admin/dashboard")
def admin_dashboard():
    """
    Purpose: Renders the central Admin Systems Console.
    Input: None
    Output: HTML template or Dashboard/Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
    if not config.is_admin():
        # Redirect standard users back to their dashboard
        return redirect(url_for('analysis.dashboard'))
        
    return render_template("admin/dashboard.html")

@admin_bp.route("/admin/users")
def admin_users():
    """
    Purpose: Renders user management table.
    Input: None
    Output: Admin protected HTML.
    """
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))
    return render_template("admin/users.html")

@admin_bp.route("/admin/feedback")
def admin_feedback_page():
    """Purpose: Admin-only feedback log viewer."""
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))
    return render_template("admin/feedback.html")

@admin_bp.route("/admin/reviews")
def admin_reviews_page():
    """Purpose: Admin-only review moderation viewer."""
    if not config.is_admin():
        return redirect(url_for('analysis.dashboard'))
    return render_template("admin/reviews.html")


# --- PUBLIC FEEDBACK UI (SESSION REQUIRED) ---

@admin_bp.route("/feedback")
def user_feedback_page():
    """
    Purpose: Allows standard users to access feedback form.
    Input: None
    Output: HTML or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
    return render_template("user/feedback.html", active_page="feedback", user=config.get_current_user())


# --- ADMIN API ROUTES (STRICT PROTECTED) ---

@admin_bp.route("/api/admin/stats")
def api_admin_stats():
    """
    Purpose: Aggregates system metrics for admins.
    Input: None (Admin check required)
    Output: JSON stats data.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    return jsonify({
        "status": "success",
        "data": {
            "users": len(config.USERS),
            "feedback_count": len(config.FEEDBACK_LOG),
            "reviews_count": len(config.REVIEWS),
            "market_state": config.MARKET_STATE["state"],
        }
    })

@admin_bp.route("/api/admin/user/all")
def api_admin_users():
    """
    Purpose: Returns exhaustive list of system users.
    Output: JSON array of user objects.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    return jsonify({"status": "success", "data": config.USERS})

@admin_bp.route("/api/admin/user/delete", methods=["DELETE"])
def api_admin_delete_user():
    """
    Purpose: Terminates a user identity.
    Input: JSON (userId)
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        user_id = str(data.get("userId") or "")
        
        remaining = [u for u in config.USERS if u["id"] != user_id]
        if len(remaining) == len(config.USERS):
            return jsonify({"status": "error", "message": "User not found."}), 404

        config.USERS.clear()
        config.USERS.extend(remaining)
        return jsonify({"status": "success", "data": {"message": "User deleted."}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@admin_bp.route("/api/admin/market/update", methods=["POST"])
def api_admin_market():
    """
    Purpose: Manipulates the global market environment.
    Input: JSON (state).
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        data = request.get_json(silent=True) or {}
        state = (data.get("state") or "").strip().lower()
        if state not in {"bullish", "stable", "bearish"}:
            return jsonify({"status": "error", "message": "Invalid state."}), 400

        config.MARKET_STATE["state"] = state
        return jsonify({"status": "success", "data": {"state": state}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@admin_bp.route("/api/admin/feedback/all")
def api_admin_feedback():
    """Purpose: Admin-only retrieval of all user feedback."""
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403
    return jsonify({"status": "success", "data": config.FEEDBACK_LOG})

@admin_bp.route("/api/admin/review/all")
def api_admin_reviews():
    """Purpose: Admin-only retrieval of all user reviews."""
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403
    return jsonify({"status": "success", "data": config.REVIEWS})


# --- USER INTERACTION API (SESSION REQUIRED) ---

@admin_bp.route("/api/admin/feedback/add", methods=["POST"])
def api_user_submit_feedback():
    """
    Purpose: Records user feedback in the persistent log.
    Input: JSON (message, subject)
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"status": "error", "message": "Message required."}), 400

        config.FEEDBACK_LOG.insert(0, {
            "user_id": config.get_current_user()["user_id"],
            "subject": (data.get("subject") or "General Inquiry").strip(),
            "message": message,
            "email": config.get_current_user()["email"],
            "created_at": "Just now",
        })
        return jsonify({"status": "success", "data": {"message": "received"}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@admin_bp.route("/api/admin/review/add", methods=["POST"])
def api_user_submit_review():
    """
    Purpose: Submits a review for moderation.
    Input: JSON (review, rating).
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        review_text = (data.get("review") or "").strip()
        if not review_text:
            return jsonify({"status": "error", "message": "Review text required."}), 400

        new_review = {
            "id": str(len(config.REVIEWS) + 1),
            "name": config.get_current_user()["username"],
            "rating": int(data.get("rating") or 5),
            "review": review_text,
            "status": "PENDING",
        }
        config.REVIEWS.insert(0, new_review)
        return jsonify({"status": "success", "data": new_review})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
