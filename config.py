"""
CONFIG.PY
----------
Shared configuration and session helpers for SmartVest.
"""
import os
from flask import session

# --- SECURITY CONFIGURATION ---

# What is SECRET_KEY?
# This is a random string used by Flask to encrypt our session cookies.
# It is needed so that users cannot tamper with their session data (like changing their user_id).
SECRET_KEY = os.getenv("SECRET_KEY", "smartvest-dev-key")


# Current global market condition
MARKET_STATE = {"state": "stable"}


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
