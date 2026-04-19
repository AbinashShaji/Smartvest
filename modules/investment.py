from flask import Blueprint, render_template, jsonify, redirect, url_for
import config
from modules.analysis import (
    analyze_stock_rows,
    filter_recommended_stocks,
    get_user_financial_snapshot,
    load_stock_csv,
)

# Create the Investment Blueprint
investment_bp = Blueprint('investment', __name__)


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


def build_live_investment_payload():
    """
    Purpose: Build the live investment payload from analysis data and stock CSV data.
    Output: Dictionary containing the investment summary and stock recommendations.
    """
    user_id = config.get_current_user()["user_id"]
    financial = get_user_financial_snapshot(user_id)

    stock_frame = load_stock_csv()
    stock_analysis, _ = analyze_stock_rows(stock_frame, generate_charts=False)
    recommended_stocks = filter_recommended_stocks(stock_analysis, financial["risk_level"])

    savings = financial["savings"]
    savings_rate = financial["savings_rate"]

    if savings <= 0:
        financial_status = "You are spending more than earning"
    elif savings_rate < 20:
        financial_status = "Low savings"
    else:
        financial_status = "Healthy financial condition"

    if financial["risk_level"] == "Low":
        advice = [
            "Build emergency fund",
            "Avoid high-risk investments",
        ]
    elif financial["risk_level"] == "Medium":
        advice = [
            "Start SIP investments",
            "Balance risk and return",
        ]
    else:
        advice = [
            "Invest in stocks",
            "Diversify portfolio",
        ]

    return {
        "financial_status": financial_status,
        "investment_suggestion": financial["investment_suggestion"],
        "risk_level": financial["risk_level"],
        "recommended_stocks": recommended_stocks,
        "advice": advice,
    }


@investment_bp.route("/api/investment/data")
def api_investment_overview():
    """
    Purpose: Provides a unified overview for user investment decisions.
    Input: None
    Output: JSON summary with market state, risk level, and stock recommendations.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        return jsonify({
            "status": "success",
            "data": build_live_investment_payload()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

