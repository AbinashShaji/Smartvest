"""
migrate_db.py
-------------
Purpose: One-time migration script for compatibility upgrades.
Run once: python migrate_db.py
"""

import sqlite3


def run():
    conn = sqlite3.connect("smartvest.db")
    cursor = conn.cursor()

    # Feedback workflow compatibility
    try:
        cursor.execute("ALTER TABLE feedback ADD COLUMN subject TEXT DEFAULT 'General Inquiry'")
        print("SUCCESS: Added feedback.subject")
    except Exception as e:
        print(f"INFO: feedback.subject - {e}")

    # Review workflow compatibility
    try:
        cursor.execute("ALTER TABLE reviews ADD COLUMN status TEXT DEFAULT 'PENDING'")
        print("SUCCESS: Added reviews.status")
    except Exception as e:
        print(f"INFO: reviews.status - {e}")

    # Goals lifecycle compatibility
    goal_columns = [
        ("status", "TEXT DEFAULT 'active'"),
        ("priority", "TEXT DEFAULT 'medium'"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
        ("paused_at", "TEXT"),
        ("completed_at", "TEXT"),
        ("archived_at", "TEXT"),
    ]
    for column_name, column_sql in goal_columns:
        try:
            cursor.execute(f"ALTER TABLE goals ADD COLUMN {column_name} {column_sql}")
            print(f"SUCCESS: Added goals.{column_name}")
        except Exception as e:
            print(f"INFO: goals.{column_name} - {e}")

    try:
        cursor.execute("UPDATE goals SET status = 'active' WHERE status IS NULL OR TRIM(status) = ''")
        cursor.execute("UPDATE goals SET priority = 'medium' WHERE priority IS NULL OR TRIM(priority) = ''")
    except Exception as e:
        print(f"INFO: goals defaults backfill - {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()

