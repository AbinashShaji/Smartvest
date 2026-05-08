"""SmartVest SQLite helpers.

Big picture:
- open SQLite connections with the same runtime path everywhere
- enable WAL mode for safer concurrent reads and writes
- create tables and indexes during startup
"""
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

import config


def get_db_connection():
    """
    Open a SQLite connection with production-safe defaults.

    Why this exists:
    Every module should use the same database path, row format, and journal
    settings so the app stays predictable.
    """
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create or upgrade tables and indexes used by SmartVest."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL,
        description TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        goal_name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        saved_amount REAL NOT NULL DEFAULT 0,
        deadline TEXT,
        status TEXT DEFAULT 'active',
        priority TEXT DEFAULT 'medium',
        created_at TEXT,
        updated_at TEXT,
        paused_at TEXT,
        completed_at TEXT,
        archived_at TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goals_user_id ON goals(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goals_deadline ON goals(deadline)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goals_created_at ON goals(created_at)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        source TEXT,
        date TEXT NOT NULL
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_income_user_id ON income(user_id)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT DEFAULT 'General Inquiry',
        message TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        accepted_at TEXT,
        resolved INTEGER DEFAULT 0
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_date ON feedback(date)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        rating INTEGER,
        comment TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        date TEXT NOT NULL,
        show_public INTEGER DEFAULT 0,
        approved_at TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_public ON reviews(show_public)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_datasets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        dataset_path TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        total_records INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 0
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_datasets_active ON market_datasets(is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_datasets_uploaded_at ON market_datasets(uploaded_at)")

    conn.commit()
    conn.close()


def create_admin():
    """
    Bootstrap the admin account from environment variables.

    Why this exists:
    Deployments can create or refresh a known admin user without storing a
    password in source code.
    """
    if not all([config.ADMIN_USERNAME, config.ADMIN_EMAIL, config.ADMIN_PASSWORD]):
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE username = ? OR email = ? OR role = 'admin'
        ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, id ASC
        LIMIT 1
        """,
        (config.ADMIN_USERNAME, config.ADMIN_EMAIL.lower()),
    )
    admin = cursor.fetchone()
    hashed_password = generate_password_hash(config.ADMIN_PASSWORD)

    if not admin:
        cursor.execute(
            """
            INSERT INTO users (username, email, password, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                config.ADMIN_USERNAME,
                config.ADMIN_EMAIL.lower(),
                hashed_password,
                "admin",
                datetime.now().strftime("%Y-%m-%d"),
            ),
        )
    else:
        # Minimal and deterministic reset:
        # keep exactly one bootstrap admin aligned with configured credentials.
        cursor.execute(
            """
            UPDATE users
            SET username = ?, email = ?, password = ?, role = 'admin'
            WHERE id = ?
            """,
            (config.ADMIN_USERNAME, config.ADMIN_EMAIL.lower(), hashed_password, admin["id"]),
        )
    conn.commit()
    conn.close()
