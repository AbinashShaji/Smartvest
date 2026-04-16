"""
review.py
---------
Purpose : Handles user-submitted reviews.
          Reviews are now saved directly to the SQLite 'reviews' table —
          no more config.REVIEWS in-memory list.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime   # Used to get the current date automatically
import config
from utils.db import get_db_connection   # Real database connection

# Create the Review Blueprint
review_bp = Blueprint('review', __name__)


# =============================================================================
# REVIEW API ROUTES  (return JSON)
# =============================================================================

@review_bp.route("/api/review/add", methods=["POST"])
def api_user_submit_review():
    """
    Purpose : Saves a new user review to the SQLite database.
              The review starts with status 'PENDING' until an admin approves it.
    Input   : JSON body with keys: "review" (required), "rating" (optional, defaults to 5)
    Output  : JSON with the newly created review object, or error message.
    """
    # Step 1: Make sure the user is logged in
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Step 2: Read the JSON data from the request body
        data = request.get_json(silent=True) or {}

        # Step 3: Get the review text and remove extra spaces
        review_text = (data.get("review") or "").strip()

        # Step 4: Review text is required — reject empty submissions
        if not review_text:
            return jsonify({"status": "error", "message": "Review text is required."}), 400

        # Step 5: Get the rating — default to 5 stars if not provided
        #         We use int() to make sure it is a whole number (1–5)
        try:
            rating = int(data.get("rating") or 5)
        except (ValueError, TypeError):
            rating = 5   # If the value is not a valid number, safely default to 5

        # Step 6: Get the integer user_id from the session
        user_id = config.get_current_user()["user_id"]

        # Step 7: Get today's date automatically
        date = datetime.now().strftime("%Y-%m-%d")

        # Step 8: Open the database and insert the new review
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO reviews (user_id, rating, comment, status, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, rating, review_text, "PENDING", date)
        )

        # Step 9: Save the changes
        conn.commit()

        # Step 10: Retrieve the newly inserted review to return to the frontend
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM reviews WHERE id = ?", (new_id,))
        new_review = dict(cursor.fetchone())

        conn.close()

        # Step 11: Return the created review as JSON
        return jsonify({"status": "success", "data": new_review})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
