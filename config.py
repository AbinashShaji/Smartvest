"""
CONFIG.PY
----------
This file acts as our simple 'Database'. 
It stores all our data in lists so that different modules can access 
and update the same information.
"""
from flask import session

# --- SECURITY CONFIGURATION ---

# What is SECRET_KEY?
# This is a random string used by Flask to encrypt our session cookies.
# It is needed so that users cannot tamper with their session data (like changing their user_id).
SECRET_KEY = "smartvest-super-secure-key-2026-cinematic"


# --- IN-MEMORY MOCK DATA (Our Temporary Database) ---

# List of all registered users
USERS = [
    {
        "id": "1",
        "username": "alex_coder",
        "email": "alex@example.com",
        "plan": "PRO",
        "joined_date": "2024-03-10",
    },
    {
        "id": "2",
        "username": "sarah_mkt",
        "email": "sarah@company.net",
        "plan": "FREE",
        "joined_date": "2024-04-01",
    },
]

# List of all user expenses
EXPENSES = [
    {"user_id": 1, "description": "Starbucks", "amount": 4.5, "category": "Food", "date": "2024-04-14"},
    {"user_id": 1, "description": "AWS Bill", "amount": 120.0, "category": "Other", "date": "2024-04-12"},
]

# List of financial goals
GOALS = [
    {"user_id": 1, "name": "Modern Apartment", "target": 50000, "deadline": "", "saved": 16000},
    {"user_id": 1, "name": "Tesla Model S", "target": 90000, "deadline": "", "saved": 9000},
]

# Log of user feedback
FEEDBACK_LOG = [
    {
        "user_id": 1,
        "subject": "Bug in Investment Chart",
        "message": "The 10-year projection doesn't seem to update when I change my SIP amount.",
        "email": "john.doe@test.com",
        "created_at": "Today, 10:45 AM",
    },
]

# User reviews for the public page
REVIEWS = [
    {
        "id": "1",
        "name": "Sarah Chen",
        "rating": 5,
        "review": "The stability indicator is a lifesaver. I finally feel in control of my financial future.",
        "status": "APPROVED",
    },
]

# Current global market condition
MARKET_STATE = {"state": "stable"}

# User income data
INCOME = {"user_id": 1, "monthly": 5200.0}


# --- AUTH HELPER FUNCTIONS ---

def get_current_user():
    """
    Purpose: Retrieve the currently logged-in user from the session.
    Input: None
    Output: Dictionary containing user_id, username, and role OR None.
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
