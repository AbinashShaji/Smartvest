"""
Purpose: SmartVest SQLite Database Handler
Handles connection, initialization, and default data setup.
"""
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

def get_db_connection():
    """
    Purpose: Create connection to SQLite database
    Input: None
    Output: Database connection object
    """
    conn = sqlite3.connect("smartvest.db")
    conn.row_factory = sqlite3.Row  # Allows accessing columns like dict
    return conn

def init_db():
    """
    Purpose: Create all tables if they do not exist
    Input: None
    Output: None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT,
        password TEXT,
        role TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]
    if "created_at" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")

    # EXPENSES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        date TEXT,
        description TEXT
    )
    """)

    # GOALS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        goal_name TEXT,
        target_amount REAL,
        saved_amount REAL,
        deadline TEXT
    )
    """)

    # INCOME TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        source TEXT,
        date TEXT
    )
    """)

    # FEEDBACK TABLE
    # Stores messages submitted by users via the feedback form
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT DEFAULT 'General Inquiry',
        message TEXT,
        date    TEXT,
        status TEXT DEFAULT 'pending',
        accepted_at TEXT,
        resolved INTEGER DEFAULT 0
    )
    """)

    # Keep feedback workflow columns compatible with older databases.
    cursor.execute("PRAGMA table_info(feedback)")
    feedback_columns = [column[1] for column in cursor.fetchall()]
    if "status" not in feedback_columns:
        cursor.execute("ALTER TABLE feedback ADD COLUMN status TEXT DEFAULT 'pending'")
    if "accepted_at" not in feedback_columns:
        cursor.execute("ALTER TABLE feedback ADD COLUMN accepted_at TEXT")
    if "resolved" not in feedback_columns:
        cursor.execute("ALTER TABLE feedback ADD COLUMN resolved INTEGER DEFAULT 0")

    # REVIEWS TABLE
    # Stores user reviews; status is PENDING until admin approves/rejects
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        rating  INTEGER,
        comment TEXT,
        status  TEXT DEFAULT 'pending',
        date    TEXT,
        show_public INTEGER DEFAULT 0,
        approved_at TEXT
    )
    """)

    # Keep review workflow columns compatible with older databases.
    cursor.execute("PRAGMA table_info(reviews)")
    review_columns = [column[1] for column in cursor.fetchall()]
    if "status" not in review_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN status TEXT DEFAULT 'pending'")
    if "show_public" not in review_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN show_public INTEGER DEFAULT 0")
    if "approved_at" not in review_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN approved_at TEXT")

    conn.commit()
    conn.close()

def create_admin():
    """
    Purpose: Ensure admin account exists in database.
    Input: None
    Output: None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    admin = cursor.fetchone()

    if not admin:
        cursor.execute("""
        INSERT INTO users (username, email, password, role, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            "admin",
            "admin@local",
            generate_password_hash("admin@7790"),
            "admin",
            datetime.now().strftime("%Y-%m-%d"),
        ))
    else:
        # Keep the seeded admin account on a hashed password even if an older DB stored plaintext.
        password = admin["password"] if "password" in admin.keys() else None
        if isinstance(password, str) and not password.startswith(("pbkdf2:", "scrypt:", "argon2:")):
            cursor.execute(
                "UPDATE users SET password = ? WHERE username = ?",
                (generate_password_hash(password), "admin")
            )

    conn.commit()
    conn.close()
