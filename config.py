"""Shared configuration and session helpers for SmartVest.

This module is the central place for runtime paths, environment-driven secrets,
and the session helpers shared across blueprints.
"""
import os
import logging
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
os.makedirs("instance", exist_ok=True)
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("smartvest")


def _is_render_production() -> bool:
    """Detect Render production without forcing local development into prod paths."""
    return os.getenv("RENDER", "").lower() == "true" or os.getenv("FLASK_ENV", "").lower() == "production"

# Why this strict secret policy exists:
# Flask signs session cookies with SECRET_KEY, so a hardcoded fallback would
# make every deployment predictable and unsafe.
SECRET_KEY = os.getenv("SECRET_KEY")

IS_PRODUCTION = _is_render_production()
ENVIRONMENT = "production" if IS_PRODUCTION else os.getenv("FLASK_ENV", "development").lower()


def _resolve_database_path() -> str:
    """Prefer Render's mounted disk when available, otherwise use the local instance DB."""
    fallback_path = INSTANCE_DIR / "smartvest.db"
    render_disk_path = (os.getenv("RENDER_DISK_PATH") or "").strip()

    if render_disk_path:
        candidate_path = Path(render_disk_path) / "smartvest.db"
        try:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("SmartVest database path resolved to Render disk: %s", candidate_path)
            return str(candidate_path)
        except OSError as exc:
            logger.warning(
                "Render disk path '%s' is unavailable or not writable (%s). Falling back to %s.",
                render_disk_path,
                exc,
                fallback_path,
            )
    else:
        logger.info("RENDER_DISK_PATH is not set. Falling back to local instance DB: %s", fallback_path)

    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    return str(fallback_path)


def _resolve_upload_base_dir() -> Path:
    """Use the same Render disk for uploads when available, otherwise keep local uploads in the repo."""
    fallback_path = BASE_DIR / "uploads"
    render_disk_path = (os.getenv("RENDER_DISK_PATH") or "").strip()

    if render_disk_path:
        candidate_path = Path(render_disk_path) / "uploads"
        try:
            candidate_path.mkdir(parents=True, exist_ok=True)
            logger.info("SmartVest upload directory resolved to Render disk: %s", candidate_path)
            return candidate_path
        except OSError as exc:
            logger.warning(
                "Render upload path '%s' is unavailable or not writable (%s). Falling back to %s.",
                candidate_path,
                exc,
                fallback_path,
            )
    else:
        logger.info("RENDER_DISK_PATH is not set. Falling back to local uploads directory: %s", fallback_path)

    fallback_path.mkdir(parents=True, exist_ok=True)
    return fallback_path


DATABASE_PATH = _resolve_database_path()
UPLOAD_BASE_DIR = _resolve_upload_base_dir()

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

