"""Shared configuration and session helpers for SmartVest."""
import os
from pathlib import Path
from flask import session

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # App still works when environment variables are injected another way.
    pass

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

# Why this strict secret policy exists:
# Flask signs session cookies with SECRET_KEY.
# A hardcoded fallback makes every deployment predictable and unsafe.
SECRET_KEY = os.getenv("SECRET_KEY")

# Why paths are configurable:
# Render and local machines can have different writable directories.
DATABASE_PATH = os.getenv("SMARTVEST_DB_PATH", str(INSTANCE_DIR / "smartvest.db"))
UPLOAD_BASE_DIR = os.getenv("SMARTVEST_UPLOAD_DIR", str(BASE_DIR / "uploads"))

# Why this flag exists:
# We can keep secure defaults while still allowing local development.
ENVIRONMENT = os.getenv("FLASK_ENV", "production").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# Why these admin values are environment-driven:
# Bootstrap credentials are sensitive and must never be hardcoded in source.
ADMIN_USERNAME = os.getenv("SMARTVEST_ADMIN_USERNAME")
ADMIN_EMAIL = os.getenv("SMARTVEST_ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("SMARTVEST_ADMIN_PASSWORD")


# --- AUTH HELPER FUNCTIONS ---

def get_current_user():
    """
    Purpose: Retrieve the currently logged-in user from the session.
    Input: None
    Output: Dictionary containing user_id, username, email, and role OR None.
    """
    return session.get("user")

def is_logged_in():
    """
    Purpose: Check if a user is currently logged in and has valid session data.
    Input: None
    Output: True if logged in with valid data, False otherwise.
    """
    return "user" in session and session["user"] is not None

def is_admin():
    """
    Purpose: Check if the currently logged-in user has an admin role for restricted access.
    Input: None
    Output: True if logged in as admin, False otherwise.
    """
    user = get_current_user()
    return bool(user and user.get("role") == "admin")

# --- COMPATIBILITY HELPERS ---

def current_user():
    """
    Purpose: Wrapper for get_current_user used in legacy templates.
    Input: None
    Output: Current user dict or guest fallback.
    """
    # Fallback to a safe guest object to prevent crashes in HTML templates
    return get_current_user() or {"user_id": None, "username": "Guest", "role": "guest"}
