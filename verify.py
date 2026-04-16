"""
verify.py  —  SmartVest End-to-End API Verification Script
Run with: python verify.py (while Flask server is running)
"""
import urllib.request
import json
import http.cookiejar

# Setup a cookie jar so the session cookie persists between requests
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

BASE = "http://127.0.0.1:5000"

def post(path, payload):
    """Send a POST request with JSON body. Returns (response_dict, status_code)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = opener.open(req, timeout=5)
        return json.loads(resp.read()), resp.getcode()
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def get(path):
    """Send a GET request. Returns (response_dict, status_code)."""
    req = urllib.request.Request(BASE + path)
    try:
        resp = opener.open(req, timeout=5)
        return json.loads(resp.read()), resp.getcode()
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

print("=" * 55)
print("  SMARTVEST FULL DATABASE VERIFICATION")
print("=" * 55)

# STEP 1: Login as admin
result, code = post("/api/auth/login", {"email": "admin", "password": "admin@7790"})
if result.get("status") == "success":
    print(f"STEP 1  Admin Login:          PASS (role={result['data']['role']})")
else:
    print(f"STEP 1  Admin Login:          FAIL — {result}")

# STEP 2: Admin stats API (reads user/feedback/review counts from DB)
result, code = get("/api/admin/stats")
if result.get("status") == "success":
    d = result["data"]
    print(f"STEP 2  Admin Stats API:      PASS | users={d['users']}  feedback={d['feedback_count']}  reviews={d['reviews_count']}  market={d['market_state']}")
else:
    print(f"STEP 2  Admin Stats API:      FAIL — {result}")

# STEP 3: Admin user list from DB
result, code = get("/api/admin/user/all")
if result.get("status") == "success":
    print(f"STEP 3  Admin Users API:      PASS | {len(result['data'])} user(s) found in DB")
else:
    print(f"STEP 3  Admin Users API:      FAIL — {result}")

# STEP 4: Dashboard data (expenses + savings from DB)
result, code = get("/api/analysis/data")
if result.get("status") == "success":
    d = result["data"]
    print(f"STEP 4  Dashboard Data API:   PASS | expenses=£{d['total_expenses']}  savings=£{d['total_savings']}")
else:
    print(f"STEP 4  Dashboard Data API:   FAIL — {result}")

# STEP 5: Analysis report (savings rate from DB)
result, code = get("/api/analysis/report")
if result.get("status") == "success":
    print(f"STEP 5  Analysis Report API:  PASS | \"{result['data']['summary']}\"")
else:
    print(f"STEP 5  Analysis Report API:  FAIL — {result}")

# STEP 6: Submit feedback → saved to DB
result, code = post("/api/feedback/add", {"subject": "Test Subject", "message": "Automated verification test"})
if result.get("status") == "success":
    print(f"STEP 6  Submit Feedback:      PASS | {result['data']['message']}")
else:
    print(f"STEP 6  Submit Feedback:      FAIL — {result}")

# STEP 7: Submit review → saved to DB
result, code = post("/api/review/add", {"review": "Great app, works perfectly!", "rating": 5})
if result.get("status") == "success":
    d = result["data"]
    print(f"STEP 7  Submit Review:        PASS | id={d['id']}  rating={d['rating']}  status={d['status']}")
else:
    print(f"STEP 7  Submit Review:        FAIL — {result}")

# STEP 8: Admin reads all feedback from DB
result, code = get("/api/admin/feedback/all")
if result.get("status") == "success":
    print(f"STEP 8  Admin Feedback API:   PASS | {len(result['data'])} record(s) in DB")
else:
    print(f"STEP 8  Admin Feedback API:   FAIL — {result}")

# STEP 9: Admin reads all reviews from DB
result, code = get("/api/admin/review/all")
if result.get("status") == "success":
    print(f"STEP 9  Admin Reviews API:    PASS | {len(result['data'])} review(s) in DB")
else:
    print(f"STEP 9  Admin Reviews API:    FAIL — {result}")

print("=" * 55)
print("  VERIFICATION COMPLETE")
print("=" * 55)
