from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import config
from utils.api_errors import safe_api_error
from utils.db import get_db_connection
from utils.mail import send_contact_email

# Public routes live here because they are the first entry point for SmartVest.
auth_bp = Blueprint('auth', __name__)

# --- PUBLIC UI ROUTES ---

@auth_bp.route("/")
def home():
    """Purpose: Renders the landing page."""
    return render_template("public/home.html")

@auth_bp.route("/about")
def about():
    """Purpose: Renders the About Us page."""
    return render_template("public/about.html")

@auth_bp.route("/reviews")
def reviews_page():
    """Purpose: Renders consumer reviews."""
    return render_template("public/reviews.html")

@auth_bp.route("/contact")
def contact():
    """Purpose: Renders Contact page."""
    return render_template("public/contact.html")


@auth_bp.route("/api/contact/send", methods=["POST"])
def api_send_contact_message():
    """
    Purpose: Sends public contact form messages to the SmartVest inbox.
    Input: JSON body with name, email, and message.
    Output: Success or validation/error message.
    """
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        message = (data.get("message") or "").strip()

        if not name or not email or not message:
            return jsonify({
                "status": "error",
                "message": "Name, email, and message are required."
            }), 400

        if len(name) > 120 or len(email) > 254 or len(message) > 4000:
            return jsonify({
                "status": "error",
                "message": "One or more fields are too long."
            }), 400

        if "@" not in email or "." not in email.split("@")[-1]:
            return jsonify({
                "status": "error",
                "message": "Please enter a valid email address."
            }), 400

        result = send_contact_email(name=name, email=email, message=message)
        return jsonify({
            "status": "success",
            "data": {
                "message": "Your message was sent successfully.",
                "recipient": result["recipient"]
            }
        }), 200
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": "Something went wrong. Please try again."
        }), 400
    except Exception as e:
        return safe_api_error(e, status_code=500)

@auth_bp.route("/login")
def login():
    """
    Purpose: Renders entry gateway.
    Input: None
    Output: HTML or Dashboard redirect.
    """
    if config.is_logged_in():
        if config.is_admin():
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('analysis.dashboard'))
    return render_template("public/login.html")

@auth_bp.route("/signup")
def signup():
    """Purpose: Renders registration gate."""
    if config.is_logged_in():
        if config.is_admin():
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('analysis.dashboard'))
    return render_template("public/signup.html")


# --- AUTHENTICATION API (SECURE) ---

def _is_hashed_password(password):
    """
    Purpose: Checks whether a password value already looks hashed.
    Input: Plain string password from the database.
    Output: True if the password appears to be a Werkzeug hash.
    """
    return isinstance(password, str) and password.startswith(("pbkdf2:", "scrypt:", "argon2:"))

def _password_matches(stored_password, candidate_password):
    """
    Purpose: Compares a stored password against a login attempt.
    Input: Stored password and candidate password strings.
    Output: True when the password is valid.
    """
    if stored_password is None:
        return False

    if _is_hashed_password(stored_password):
        return check_password_hash(stored_password, candidate_password)

    return stored_password == candidate_password

def _build_session_user(user_row):
    """
    Purpose: Creates the standard session user payload.
    Input: SQLite row containing user data.
    Output: Dictionary with user_id, username, email, and role.
    """
    return {
        "user_id": user_row["id"],
        "username": user_row["username"],
        "email": user_row["email"],
        "role": user_row["role"],
    }

@auth_bp.route("/api/auth/signup", methods=["POST"])
def api_signup():
    """Create a new user account and start a signed-in session."""
    """
    Purpose: Creates a new user account and starts a logged-in session.
    Input: JSON body with username, email, and password.
    Output: Created user object or error message.
    """
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not username or not email or not password:
            return jsonify({
                "status": "error",
                "message": "Username, email, and password are required."
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        )
        existing_user = cursor.fetchone()
        if existing_user is not None:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "A user with that username or email already exists."
            }), 409

        hashed_password = generate_password_hash(password)
        cursor.execute(
            """
            INSERT INTO users (username, email, password, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, email, hashed_password, "user", datetime.now().strftime("%Y-%m-%d"))
        )
        conn.commit()

        user_id = cursor.lastrowid
        cursor.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,))
        new_user = cursor.fetchone()
        conn.close()

        session.clear()
        session["user"] = _build_session_user(new_user)
        session.permanent = True
        session.modified = True

        return jsonify({
            "status": "success",
            "data": session["user"]
        }), 201
    except Exception as e:
        return safe_api_error(e, status_code=500)

@auth_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    """Authenticate a user and persist the session payload."""
    """
    Purpose: Authenticates user credentials and establishes secure session.
    Input: JSON (email, password)
    Output: Success user object or Error message.
    """
    try:
        # 1. Validation: Ensure JSON data exists
        data = request.get_json(silent=True) or {}
        username_input = (data.get("email") or "").strip()
        password = data.get("password")

        if not username_input or not password:
            return jsonify({
                "status": "error", 
                "message": "Username/Email and password are required."
            }), 400

        # 2. Database logic: Verify credentials
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username_input, username_input.lower())
        )
        user = cursor.fetchone()

        if user is None:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Invalid credentials."
            }), 401

        if not _password_matches(user["password"], password):
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Invalid credentials."
            }), 401

        # If the database still has an old plaintext password, upgrade it now.
        if not _is_hashed_password(user["password"]):
            cursor.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(user["password"]), user["id"])
            )
            conn.commit()

        conn.close()

        session.clear()
        session["user"] = _build_session_user(user)
        session.permanent = True 
        session.modified = True
        
        return jsonify({
            "status": "success", 
            "data": session["user"]
        })
    except Exception as e:
        return safe_api_error(e, status_code=500)

@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """Clear the active session so the browser is fully signed out."""
    """
    Purpose: Terminates user session.
    Input: None
    Output: Success message.
    """
    try:
        session.clear()
        return jsonify({
            "status": "success", 
            "data": {"message": "Logged out successfully."}
        })
    except Exception as e:
        return safe_api_error(e, status_code=500)

@auth_bp.route("/api/auth/check-session")
def api_check_session():
    """Return the active session payload if the browser is still signed in."""
    """
    Purpose: Verifies if a user session is still alive.
    Input: None
    Output: User data or 401 Unauthorized.
    """
    if config.is_logged_in():
        return jsonify({
            "status": "success", 
            "data": config.get_current_user()
        })
    
    return jsonify({
        "status": "error", 
        "message": "No active session."
    }), 401


# --- PROFILE ACTIONS (SECURE) ---

@auth_bp.route("/api/auth/profile/update", methods=["POST"])
def api_update_profile():
    """Update the logged-in user's profile details."""
    """
    Purpose: Modifies user attributes in session and database.
    Input: JSON with 'username' and optionally 'email'
    Output: JSON success message with updated user data
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip()
        
        if not username:
            return jsonify({"status": "error", "message": "Username is required."}), 400

        # Get the ID of the logged-in user
        user_id = session["user"]["user_id"]

        # Update the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if email:
            cursor.execute("UPDATE users SET username = ?, email = ? WHERE id = ?", (username, email.lower(), user_id))
        else:
            cursor.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
        
        cursor.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,))
        updated_user = cursor.fetchone()
        conn.commit()
        conn.close()

        # Update persistent session
        session["user"] = _build_session_user(updated_user)
        session.modified = True
        
        return jsonify({
            "status": "success", 
            "data": config.get_current_user()
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)

@auth_bp.route("/api/auth/password/change", methods=["POST"])
def api_change_password():
    """Change the logged-in user's password after verifying the current one."""
    """
    Purpose: Update the logged-in user's password in the database.
    Input: JSON with 'new_password'
    Output: JSON success or error message
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Get JSON data from the request
        data = request.get_json(silent=True) or {}
        current_password = data.get("current_password") or ""
        new_password = data.get("new_password")
        
        # Check if new password is provided
        if not new_password:
            return jsonify({"status": "error", "message": "New password is required."}), 400

        # Get the current user's ID
        user_id = session["user"]["user_id"]

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT password FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if user_row is None:
            conn.close()
            return jsonify({"status": "error", "message": "User not found."}), 404

        stored_password = user_row["password"]
        if not current_password or not _password_matches(stored_password, current_password):
            conn.close()
            return jsonify({"status": "error", "message": "Current password is incorrect."}), 400

        # Execute simple SQL update query with a hashed password
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (generate_password_hash(new_password), user_id))
        
        # Save changes and close database connection
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success", 
            "data": {"message": "Password updated successfully."}
        })
    except Exception as e:
        return safe_api_error(e, status_code=400)


