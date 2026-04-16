from flask import Blueprint, render_template, jsonify, redirect, url_for
import config

# Create the Investment Blueprint
investment_bp = Blueprint('investment', __name__)

# --- UI PAGE ROUTES (PROTECTED) ---

@investment_bp.route("/investment")
def investment():
    """
    Purpose: Renders the Investment Suggestions page.
    Input: None
    Output: HTML template or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
        
    return render_template("user/investment.html", active_page="investment", user=config.get_current_user())


# --- INVESTMENT API (PROTECTED) ---
# Prefix: /api/investment/

@investment_bp.route("/api/investment/data")
def api_investment_overview():
    """
    Purpose: Provides a unified overview for user investment decisions.
    Input: None
    Output: JSON summary with market state and strategies.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    try:
        return jsonify({
            "status": "success",
            "data": {
                "market_state": config.MARKET_STATE["state"],
                "strategies": get_mock_strategies()
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@investment_bp.route("/api/investment/strategy/all")
def api_investment_strategies():
    """
    Purpose: Returns the exhaustive list of current investment strategies.
    Input: None
    Output: JSON array of strategy objects.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401
        
    return jsonify({
        "status": "success",
        "data": get_mock_strategies()
    })

@investment_bp.route("/api/investment/market/status")
def api_market_status():
    """
    Purpose: Returns the live global market state.
    Input: None
    Output: JSON object containing 'state'.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401
        
    return jsonify({
        "status": "success",
        "data": {"state": config.MARKET_STATE["state"]}
    })


# --- HELPERS ---

def get_mock_strategies():
    """
    Purpose: Returns a hardcoded list of professional investment options.
    Output: List of strategy dictionaries.
    """
    return [
        {"title": "Fixed Deposit Plus", "risk": "Low", "return_rate": "7.5%"},
        {"title": "Automated SIP", "risk": "Moderate", "return_rate": "12-15%"},
        {"title": "Dynamic Stock Pick", "risk": "High", "return_rate": "Variable"},
    ]
