"""Shared configuration and session helpers for SmartVest.

This module is the central place for runtime paths, environment-driven secrets,
and the session helpers shared across blueprints.
"""
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
# Flask signs session cookies with SECRET_KEY, so a hardcoded fallback would
# make every deployment predictable and unsafe.
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
    What this function does:
    Returns the logged-in user stored in Flask session data.

    Why this exists:
    Many routes need the same current-user lookup, so this keeps that logic in
    one place instead of repeating session access everywhere.

    Inputs:
    None.

    Returns:
    A dictionary with user_id, username, email, and role, or None.
    """
    return session.get("user")

def is_logged_in():
    """
    What this function does:
    Checks whether the current browser session has a logged-in user.

    Why this exists:
    Route guards need a simple and readable way to ask "is this user signed in?"

    Inputs:
    None.

    Returns:
    True when the session contains a user object, otherwise False.
    """
    return "user" in session and session["user"] is not None

def is_admin():
    """
    What this function does:
    Checks whether the logged-in user has admin permissions.

    Why this exists:
    Admin pages and admin APIs should all use the same role check so the rule
    stays consistent across the app.

    Inputs:
    None.

    Returns:
    True when the current session user has role == "admin".
    """
    user = get_current_user()
    return bool(user and user.get("role") == "admin")

