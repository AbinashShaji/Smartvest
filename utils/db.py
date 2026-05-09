"""SmartVest SQLite helpers.

Big picture:
- open SQLite connections with the same runtime path everywhere
- enable WAL mode for safer concurrent reads and writes
- create tables and indexes during startup
"""
import logging
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

import config


logger = logging.getLogger("smartvest")


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
    Deployments can create a known admin user without storing a password in
    source code.
    """
    username = (config.ADMIN_USERNAME or "").strip()
    password = config.ADMIN_PASSWORD or ""
    email = (config.ADMIN_EMAIL or "").strip().lower()

    if not username or not password:
        logger.info("Admin bootstrap skipped: ADMIN_USERNAME and ADMIN_PASSWORD are not configured.")
        return False

    if not email:
        email = username if "@" in username else f"{username}@smartvest.local"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE role = 'admin'
        ORDER BY id ASC
        LIMIT 1
        """,
        (),
    )
    admin = cursor.fetchone()
    if admin:
        logger.info("Admin bootstrap skipped: existing admin user already present (id=%s).", admin["id"])
        conn.close()
        return False

    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE username = ? OR email = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (username, email),
    )
    conflict = cursor.fetchone()
    if conflict:
        logger.warning(
            "Admin bootstrap skipped: username or email already exists (user id=%s).",
            conflict["id"],
        )
        conn.close()
        return False

    hashed_password = generate_password_hash(password)
    cursor.execute(
        """
        INSERT INTO users (username, email, password, role, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            username,
            email,
            hashed_password,
            "admin",
            datetime.now().strftime("%Y-%m-%d"),
        ),
    )
    conn.commit()
    conn.close()
    logger.info("Admin bootstrap complete: created admin user '%s'.", username)
    return True
