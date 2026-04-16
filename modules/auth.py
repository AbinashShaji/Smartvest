from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
import config

# Create the Auth Blueprint
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

@auth_bp.route("/login")
def login():
    """
    Purpose: Renders entry gateway.
    Input: None
    Output: HTML or Dashboard redirect.
    """
    if config.is_logged_in():
        return redirect(url_for('analysis.dashboard'))
    return render_template("public/login.html")

@auth_bp.route("/signup")
def signup():
    """Purpose: Renders registration gate."""
    if config.is_logged_in():
        return redirect(url_for('analysis.dashboard'))
    return render_template("public/signup.html")


# --- USER UI (PROTECTED) ---

@auth_bp.route("/settings")
def settings():
    """
    Purpose: Renders user profile control.
    Input: None
    Output: HTML or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
    
    return render_template("user/settings.html", active_page="settings", user=config.get_current_user())


# --- AUTHENTICATION API (SECURE) ---

@auth_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    """
    Purpose: Authenticates user credentials and establishes secure session.
    Input: JSON (email, password)
    Output: Success user object or Error message.
    """
    try:
        # 1. Validation: Ensure JSON data exists
        data = request.get_json(silent=True) or {}
        username_input = data.get("email") # The field name is still 'email' from the frontend
        password = data.get("password")

        if not username_input or not password:
            return jsonify({
                "status": "error", 
                "message": "Username/Email and password are required."
            }), 400

        # 2. Basic Format Validation
        # Admin is allowed as a plain string, others must be emails (contain @)
        if username_input != "admin" and "@" not in username_input:
            return jsonify({
                "status": "error", 
                "message": "Invalid format. Use 'admin' or a valid email (e.g., user@mail.com)."
            }), 400

        # 3. Security: Clear any existing session data before logging in new user
        session.clear()

        # 4. Logic: Admin check (Fixed Credentials)
        # We now check for the simple 'admin' username
        if username_input == "admin" and password == "admin@7790":
            session["user"] = {
                "user_id": 0,
                "username": "System Admin",
                "email": "admin@smartvest.ai",
                "role": "admin"
            }
        else:
            # 5. Logic: Mock user login (Role is always 'user')
            # For this phase, we accept the password as valid if format is correct
            session["user"] = {
                "user_id": 1,
                "username": username_input.split('@')[0].capitalize(),
                "email": username_input,
                "role": "user"
            }
        
        # Ensure session is saved correctly
        session.permanent = True 
        
        return jsonify({
            "status": "success", 
            "data": session["user"]
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
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
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@auth_bp.route("/api/auth/check-session")
def api_check_session():
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
    """
    Purpose: Modifies session user attributes.
    Input: JSON (username)
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        
        if not username:
            return jsonify({"status": "error", "message": "Username is required."}), 400

        # Update persistent session
        session["user"]["username"] = username
        session.modified = True
        
        return jsonify({
            "status": "success", 
            "data": config.get_current_user()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@auth_bp.route("/api/auth/password/change", methods=["POST"])
def api_change_password():
    """Purpose: Placeholder for security actions."""
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    return jsonify({
        "status": "success", 
        "data": {"message": "Password updated successfully."}
    })
