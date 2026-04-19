"""
APP.PY - SmartVest Main Entry Point
-----------------------------------
This is the heart of our Flask application. 
During refactoring, we have moved all the messy code into 'Modules'.
This file now stays clean and only handles connecting everything together.
"""
import config
from flask import Flask, jsonify

# 1. Initialize the Flask Application
from utils.db import init_db, create_admin
init_db()
create_admin()

app = Flask(__name__)
# SECRET_KEY is managed in config.py for better organization.
app.secret_key = config.SECRET_KEY

# 2. Import our Blueprints from the 'modules' folder
# Each blueprint handles a specific part of the app (e.g., Auth, Expenses)
from modules.auth import auth_bp
from modules.expense import expense_bp
from modules.analysis import analysis_bp
from modules.investment import investment_bp
from modules.admin import admin_bp
from modules.settings import settings_bp
from modules.feedback import feedback_bp
from modules.review import review_bp
from modules.analysis import build_market_metrics

# 3. Register our Blueprints with the App
# This 'plugs in' the routes from our module files into app.py
app.register_blueprint(auth_bp)
app.register_blueprint(expense_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(investment_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(review_bp)


@app.route("/api/admin/market-metrics")
def api_admin_market_metrics():
    """
    Purpose : Returns live market metrics derived from data/stock.csv.
    Input   : None
    Output  : JSON with summary, market status, movers, counts, and chart paths.
    """
    if not config.is_admin():
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        return jsonify({
            "status": "success",
            "data": build_market_metrics()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# 4. Start the Application
if __name__ == "__main__":
    # We run in debug mode so the server restarts when we save changes
    app.run(debug=True)
