"""
migrate_db.py
-------------
Purpose : One-time migration script.
          Adds missing columns to feedback and reviews tables
          so the new code works correctly.
Run once: python migrate_db.py
"""
import sqlite3

# Open the database
conn = sqlite3.connect("smartvest.db")
cursor = conn.cursor()

# --- Add 'subject' column to feedback table ---
# This stores the topic/subject of the feedback (e.g. "Bug Report")
try:
    cursor.execute("ALTER TABLE feedback ADD COLUMN subject TEXT DEFAULT 'General Inquiry'")
    print("SUCCESS: Added 'subject' column to feedback table.")
except Exception as e:
    print(f"INFO: feedback.subject — {e}")

# --- Add 'status' column to reviews table ---
# This stores the moderation status (PENDING / APPROVED / REJECTED)
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN status TEXT DEFAULT 'PENDING'")
    print("SUCCESS: Added 'status' column to reviews table.")
except Exception as e:
    print(f"INFO: reviews.status — {e}")

# Save all changes
conn.commit()
conn.close()

print("\nMigration complete. You can now run the app.")
