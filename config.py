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
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)


def _is_render_production() -> bool:
    """Detect Render production without forcing local development into prod paths."""
    return os.getenv("RENDER", "").lower() == "true" or os.getenv("FLASK_ENV", "").lower() == "production"

# Why this strict secret policy exists:
# Flask signs session cookies with SECRET_KEY, so a hardcoded fallback would
# make every deployment predictable and unsafe.
SECRET_KEY = os.getenv("SECRET_KEY")

# Why paths are configurable:
# Render and local machines can have different writable directories.
IS_PRODUCTION = _is_render_production()
ENVIRONMENT = "production" if IS_PRODUCTION else os.getenv("FLASK_ENV", "development").lower()
DATABASE_PATH = os.getenv(
    "SMARTVEST_DB_PATH",
    "/var/data/smartvest.db" if IS_PRODUCTION else str(INSTANCE_DIR / "smartvest.db"),
)
UPLOAD_BASE_DIR = Path(
    os.getenv(
        "SMARTVEST_UPLOAD_DIR",
        "/var/data/uploads" if IS_PRODUCTION else str(BASE_DIR / "uploads"),
    )
)

Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
UPLOAD_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Why these admin values are environment-driven:
# Bootstrap credentials are sensitive and must never be hardcoded in source.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME") or os.getenv("SMARTVEST_ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or os.getenv("SMARTVEST_ADMIN_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL") or os.getenv("SMARTVEST_ADMIN_EMAIL")

if not ADMIN_EMAIL and ADMIN_USERNAME:
    ADMIN_EMAIL = ADMIN_USERNAME if "@" in ADMIN_USERNAME else f"{ADMIN_USERNAME}@smartvest.local"


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
    if not user or user.get("role") != "admin":
        return False

    try:
        from utils.db import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, role FROM users WHERE id = ?", (user.get("user_id"),))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            session.pop("user", None)
            return False

        if row["role"] != "admin":
            session["user"] = {
                **user,
                "role": row["role"],
            }
            session.modified = True
            return False

        return True
    except Exception:
        return False

