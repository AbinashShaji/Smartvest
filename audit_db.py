import sqlite3
from werkzeug.security import check_password_hash

def audit_db(path, label):
    print(f"\n{'='*50}")
    print(f"DB: {label} ({path})")
    print(f"{'='*50}")
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        print(f"Tables: {tables}")

        if "users" in tables:
            c.execute("PRAGMA table_info(users)")
            cols = [r["name"] for r in c.fetchall()]
            print(f"Columns: {cols}")
            c.execute("SELECT id, username, email, role, password FROM users")
            rows = c.fetchall()
            print(f"User count: {len(rows)}")
            for r in rows:
                pw = r["password"] or ""
                hash_type = pw.split(":")[0] if pw else "EMPTY"
                print(f"  id={r['id']} username={r['username']} email={r['email']} role={r['role']} hash_type={hash_type}")
                if r["username"] == "admin":
                    result = check_password_hash(pw, "admin123")
                    print(f"  >>> Admin password 'admin123' match: {result}")
        else:
            print("No users table found!")
        conn.close()
    except Exception as e:
        print(f"ERROR accessing {path}: {e}")

audit_db("smartvest.db", "ROOT")
audit_db("instance/smartvest.db", "INSTANCE")
