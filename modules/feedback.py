"""
feedback.py
-----------
Purpose : Handles the user feedback page and the API that saves feedback to the database.
          No more config.FEEDBACK_LOG — data is now stored in the SQLite 'feedback' table.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime   # Used to get today's date automatically
import config
from utils.db import get_db_connection   # Real database connection

# Create the Feedback Blueprint
feedback_bp = Blueprint('feedback', __name__)


# =============================================================================
# UI PAGE ROUTES  (return HTML pages)
# =============================================================================

@feedback_bp.route("/feedback")
def user_feedback_page():
    """
    Purpose : Renders the Feedback form page for logged-in users.
    Input   : None
    Output  : HTML page, or redirect to login if not logged in.
    """
    # Only logged-in users can submit feedback
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/feedback.html",
        active_page="feedback",
        user=config.get_current_user()
    )


# =============================================================================
# FEEDBACK API ROUTES  (return JSON)
# =============================================================================

@feedback_bp.route("/api/feedback/add", methods=["POST"])
def api_user_submit_feedback():
    """
    Purpose : Saves a new feedback message to the SQLite database.
              Uses user_id from the session — NOT email (email is not in the session).
    Input   : JSON body with keys: "message" (required), "subject" (optional)
    Output  : JSON success message, or error if something goes wrong.
    """
    # Step 1: Make sure the user is logged in before accepting any data
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Step 2: Read the JSON data sent by the frontend form
        data = request.get_json(silent=True) or {}

        # Step 3: Get the message text and remove extra spaces
        message = (data.get("message") or "").strip()

        # Step 4: Message is required — reject empty submissions
        if not message:
            return jsonify({"status": "error", "message": "Feedback message is required."}), 400

        # Step 5: Get the subject, default to "General Inquiry" if not provided
        subject = (data.get("subject") or "General Inquiry").strip()

        # Step 6: Get the integer user_id from the session
        #         We use user_id — NOT email (email is not stored in the session)
        user_id = config.get_current_user()["user_id"]

        # Step 7: Get today's date automatically — no more hardcoded dates
        date = datetime.now().strftime("%Y-%m-%d")

        # Step 8: Open the database connection and save the feedback
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO feedback (user_id, message, subject, date) VALUES (?, ?, ?, ?)",
            (user_id, message, subject, date)
        )

        # Step 9: Commit (save) the change to the database
        conn.commit()
        conn.close()

        # Step 10: Return success to the frontend
        return jsonify({"status": "success", "data": {"message": "Feedback received. Thank you!"}})

    except Exception as e:
        # If anything fails, return the error so it can be debugged
        return jsonify({"status": "error", "message": str(e)}), 400
