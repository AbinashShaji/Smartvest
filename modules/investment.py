"""
investment.py
-------------
Purpose : Full investment assistant module for SmartVest.
           Phases 3–7: Investment readiness, allocation, promotion,
           enriched stock recommendations, and SIP growth projections.

Design  : ALL data comes from get_analysis_data() — the single source of truth.
           This module contains ZERO database queries of its own.
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for
import config
from modules.analysis import (
    get_analysis_data,
    analyze_stock_rows,
    filter_recommended_stocks,
    get_risk_level,
    load_stock_csv,
)

# ── Blueprint Registration ──────────────────────────────────────────────────
investment_bp = Blueprint('investment', __name__)


# =============================================================================
# PHASE 3 — DECISION ENGINE
# =============================================================================

def get_decision_engine(analysis: dict) -> dict:
    behavior = analysis.get("savings_behavior") or {}
    emergency = analysis.get("emergency") or {}
    
    avg_savings = behavior.get("avg_savings", 0.0)
    ef_progress = emergency.get("progress_percent", 0.0)
    ef_remaining = emergency.get("remaining", 0.0)
    stable = behavior.get("stable", False)
    
    reasons = []
    actions = []
    
    if avg_savings > 0 and ef_remaining > 0:
        months_to_fund = round(ef_remaining / avg_savings)
        time_to_ready = f"{months_to_fund} months"
    elif ef_remaining == 0:
        time_to_ready = "Ready Now"
    else:
        time_to_ready = "Unknown (No Savings)"
    
    if ef_progress < 25:
        decision = "NOT_READY"
        impact = "Your emergency fund is critically low. Investing now could force you to sell at a loss in an emergency."
        confidence = 90
        next_step = "Focus 100% of savings on building at least 25% of your emergency-fund target."
        reasons.append(f"Emergency fund is only {ef_progress:.1f}% complete (minimum 25% required).")
        if not stable:
            reasons.append("Savings pattern is highly volatile.")
        actions.append("Halt all investments immediately.")
        actions.append(f"Redirect all available funds to reach the {emergency.get('target', 0):,.0f} emergency-fund target.")
    elif ef_progress <= 75:
        decision = "PARTIAL"
        impact = "You have a basic safety net. You can start investing a small portion while continuing to build your emergency fund."
        confidence = 85
        next_step = "Start a small SIP while directing the rest to your emergency fund."
        reasons.append(f"Emergency fund is {ef_progress:.1f}% complete (target range is 25% to 75%).")
        actions.append("Allocate 30% of savings to investments.")
        actions.append("Direct the remaining 70% to complete your emergency fund.")
    else:
        decision = "READY"
        impact = "Your safety net is strong. You are fully prepared to aggressively grow your wealth."
        confidence = 95
        next_step = "Maximize your SIP contributions and explore growth opportunities."
        time_to_ready = "Ready Now"
        reasons.append(f"Emergency fund is {ef_progress:.1f}% complete and above the readiness threshold.")
        if stable:
            reasons.append("Savings are stable.")
        actions.append("Allocate 60% of savings to your portfolio.")
        actions.append("Keep 40% as a liquid buffer for lifestyle spending or short-term goals.")
            
    return {
        "decision": decision,
        "reasons": reasons,
        "impact": impact,
        "actions": actions,
        "next_step": next_step,
        "time_to_ready": time_to_ready,
        "confidence": confidence
    }


# =============================================================================
# PHASE 4 — SIP ENGINE
# =============================================================================

def get_sip_engine(analysis: dict, decision_engine: dict) -> dict:
    decision = decision_engine.get("decision", "NOT_READY")
    behavior = analysis.get("savings_behavior") or {}
    emergency = analysis.get("emergency") or {}
    avg_savings = behavior.get("avg_savings", 0.0)
    current = analysis.get("current") or {}
    
    savings_rate = current.get("savings_rate", 0.0)
    
    if decision == "NOT_READY":
        risk_level = "Low"
    elif decision == "PARTIAL":
        risk_level = "Moderate"
    else:
        risk_level = "High" if savings_rate >= 30 else "Medium"
        
    if risk_level == "Low":
        alloc_pct = {"Nifty 50": 100, "Nifty 100": 0, "Midcap": 0}
        reasoning = "100% Large Cap focus to preserve capital while you build stability."
    elif risk_level in ["Moderate", "Medium"]:
        alloc_pct = {"Nifty 50": 60, "Nifty 100": 40, "Midcap": 0}
        reasoning = "Balanced mix of Top 50 and Top 100 companies for steady growth."
    else:
        alloc_pct = {"Nifty 50": 50, "Nifty 100": 30, "Midcap": 20}
        reasoning = "Includes 20% Midcap allocation to maximize long-term wealth generation."

    if decision == "NOT_READY":
        recommended_start = round(avg_savings * 0.6, 2)
        ef_remaining = emergency.get("remaining", 0.0)
        message = f"Save ₹{ef_remaining:,.0f} more to start investing."
        return {
            "sip_status": "not_ready",
            "sip_amount": 0.0,
            "message": message,
            "recommended_start": recommended_start,
            "time_to_ready": decision_engine.get("time_to_ready", "Unknown"),
            "risk_level": risk_level,
            "allocation": {
                "allocation_percent": alloc_pct,
                "allocation_amount": {"Nifty 50": 0, "Nifty 100": 0, "Midcap": 0},
                "reasoning": reasoning
            }
        }
    
    if decision == "PARTIAL":
        invest = round(avg_savings * 0.3, 2)
        full_sip = round(avg_savings * 0.6, 2)
        alloc_amount = {k: round(invest * (v / 100), 2) for k, v in alloc_pct.items()}
        return {
            "sip_status": "partial",
            "sip_amount": invest,
            "safe_sip": invest,
            "full_sip": full_sip,
            "explanation": f"We recommend a partial SIP of ₹{invest:,.0f} (30% of savings) to start the compounding habit, while you direct the remaining 70% to finish your emergency fund.",
            "risk_level": risk_level,
            "allocation": {
                "allocation_percent": alloc_pct,
                "allocation_amount": alloc_amount,
                "reasoning": reasoning
            }
        }

    # READY
    invest = round(avg_savings * 0.6, 2)
    alloc_amount = {k: round(invest * (v / 100), 2) for k, v in alloc_pct.items()}
    return {
        "sip_status": "ready",
        "sip_amount": invest,
        "safe_sip": invest,
        "full_sip": invest,
        "explanation": f"You are ready! A full SIP of ₹{invest:,.0f} (60% of savings) will optimally balance aggressive growth with a comfortable 40% lifestyle buffer.",
        "risk_level": risk_level,
        "allocation": {
            "allocation_percent": alloc_pct,
            "allocation_amount": alloc_amount,
            "reasoning": reasoning
        }
    }


def get_what_if_analysis(analysis: dict, sip_engine: dict) -> dict:
    current = analysis.get("current") or {}
    expense = current.get("expense", 0.0)
    current_sip = sip_engine.get("sip_amount", 0.0)
    
    # Simulate: Reduce spending by 10% -> increase SIP
    savings_boost = expense * 0.10
    new_sip = current_sip + savings_boost
    
    rate = 0.12 # moderate rate
    current_proj = sip_future_value(current_sip, rate, 60).get("final_value", 0.0)
    new_proj = sip_future_value(new_sip, rate, 60).get("final_value", 0.0)
    gain_diff = new_proj - current_proj
    
    return {
        "scenario": "Cut expenses by 10%",
        "new_sip": round(new_sip, 2),
        "new_projection_5y": round(new_proj, 2),
        "gain_difference": round(gain_diff, 2),
        "message": f"If you reduce your monthly expenses by 10% (₹{savings_boost:,.0f}), you can increase your SIP to ₹{new_sip:,.0f}. This simple change could add ₹{gain_diff:,.0f} to your portfolio over 5 years!"
    }


# =============================================================================
# PHASE 5 — ALERTS
# =============================================================================

def get_alerts(analysis: dict) -> list:
    alerts = []
    behavior = analysis.get("savings_behavior") or {}
    current = analysis.get("current") or {}
    
    if behavior.get("volatility", 0.0) > 0.35:
        alerts.append({"message": "High savings volatility detected.", "severity": "warning"})
    
    if behavior.get("trend") == "decreasing":
        alerts.append({"message": "Savings have been dropping recently.", "severity": "warning"})
        
    if current.get("savings", 0.0) < 0:
        alerts.append({"message": "Overspending detected! Expenses exceed income.", "severity": "critical"})
        
    return alerts



# =============================================================================
# PHASE 6 — ENRICHED STOCK OUTPUT
# =============================================================================

def _enrich_stock(stock: dict, risk_level: str) -> dict:
    """
    Purpose : Add trend, reason, risk_fit, and confidence to a stock entry.
    Input   : Raw stock dict from analyze_stock_rows, user's risk_level.
    Output  : Enriched stock dict.
    """
    change = stock.get("change", 0.0)
    status = stock.get("status", "Stable")
    prices = stock.get("prices", [])

    # ── Trend description ──
    if change > 10:
        trend = "Strong Uptrend"
    elif change > 5:
        trend = "Uptrend"
    elif change < -10:
        trend = "Strong Downtrend"
    elif change < -5:
        trend = "Downtrend"
    else:
        trend = "Sideways"

    # ── Reason for recommendation ──
    if status == "Good":
        reason = "Consistent price growth over the observed period."
    elif status == "Stable":
        reason = "Low volatility with steady price movement."
    else:
        reason = "Currently declining — included for awareness only."

    # ── Risk fit — does the stock match the user's risk level? ──
    fit_map = {
        "Low": {"Stable"},
        "Medium": {"Stable", "Good"},
        "High": {"Good"},
    }
    allowed = fit_map.get(risk_level, {"Stable"})
    risk_fit = "Match" if status in allowed else "Mismatch"

    # ── Confidence score (0–100) ──
    # Simple heuristic: based on change magnitude and consistency
    if len(prices) >= 2:
        # Count how many consecutive days moved in the same direction
        ups = sum(1 for i in range(1, len(prices)) if prices[i] >= prices[i - 1])
        consistency = ups / (len(prices) - 1)  # 0 to 1
    else:
        consistency = 0.5

    raw_confidence = consistency * 100
    if risk_fit == "Mismatch":
        raw_confidence *= 0.5  # Penalize mismatch
    confidence = round(min(100, max(0, raw_confidence)))

    return {
        "name": stock.get("name", "Unknown"),
        "status": status,
        "change": round(change, 2),
        "prices": prices,
        "chart": stock.get("chart", ""),
        "trend": trend,
        "reason": reason,
        "risk_fit": risk_fit,
        "confidence": confidence,
    }


# =============================================================================
# PHASE 7 — SIP GROWTH + COMPARISON
# =============================================================================

# Annual return rates for different investment types
RETURN_RATES = {
    "savings": 0.04,    # 4% — bank savings account
    "safe": 0.08,       # 8% — debt funds / FDs
    "moderate": 0.12,   # 12% — balanced / index funds
    "high": 0.15,       # 15% — equity / direct stocks
}


def sip_future_value(monthly_amount: float, annual_rate: float, months: int) -> dict:
    """
    Purpose : Project the future value of a monthly SIP investment.
    Formula : FV = P × [((1+r)^n − 1) / r] × (1+r)
              where r = monthly rate, n = total months, P = monthly amount.
    Input   : monthly_amount, annual_rate (decimal), months.
    Output  : Dictionary with final_value, invested, profit, percentage, diff_vs_savings.
    """
    if monthly_amount <= 0 or annual_rate <= 0 or months <= 0:
        return {
            "final_value": 0.0,
            "invested": 0.0,
            "profit": 0.0,
            "percentage": 0.0,
            "diff_vs_savings": 0.0,
        }

    monthly_rate = annual_rate / 12       # Convert annual to monthly
    
    # Standard SIP future value formula
    if monthly_rate > 0:
        fv = monthly_amount * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
    else:
        fv = monthly_amount * months

    invested = monthly_amount * months
    profit = fv - invested
    percentage = (profit / invested) * 100 if invested > 0 else 0.0

    savings_rate = 0.04 / 12 # 4%
    savings_fv = monthly_amount * (((1 + savings_rate) ** months - 1) / savings_rate) * (1 + savings_rate)
    diff_vs_savings = fv - savings_fv

    return {
        "final_value": round(fv, 2),
        "invested": round(invested, 2),
        "profit": round(profit, 2),
        "percentage": round(percentage, 2),
        "diff_vs_savings": round(diff_vs_savings, 2),
    }


def build_growth_comparison(sip_engine: dict) -> dict:
    """
    Purpose : Compare growth of savings vs safe vs moderate vs high investments.
    Input   : SIP Engine dictionary.
    Output  : Dictionary with 1-year and 5-year projections for each type.
    """
    invest_amount = sip_engine.get("sip_amount", 0.0)
    
    if invest_amount <= 0:
        potential_sip = sip_engine.get("recommended_start", 0.0)
        time_str = sip_engine.get("time_to_ready", "a few months")
        comparison = {
            "is_potential": True, 
            "potential_sip": potential_sip, 
            "time_to_ready": time_str, 
            "sip_amount": 0,
            "total_invested_1y": potential_sip * 12,
            "total_invested_5y": potential_sip * 60,
            "explanation": f"You can start with ₹{potential_sip:,.0f}/month after {time_str} and reach significant wealth in 5 years.",
            "data": {}
        }
        for label, rate in RETURN_RATES.items():
            year_1 = sip_future_value(potential_sip, rate, 12)
            year_5 = sip_future_value(potential_sip, rate, 60)
            comparison["data"][label] = {
                "rate": round(rate * 100, 1),
                "year_1": year_1,
                "year_5": year_5,
            }
        return comparison

    comparison = {
        "is_potential": False, 
        "sip_amount": invest_amount,
        "total_invested_1y": invest_amount * 12,
        "total_invested_5y": invest_amount * 60,
        "explanation": f"This projection assumes you invest ₹{invest_amount:,.0f} per month for the chosen duration.",
        "data": {}
    }
    for label, rate in RETURN_RATES.items():
        year_1 = sip_future_value(invest_amount, rate, 12)
        year_5 = sip_future_value(invest_amount, rate, 60)

        comparison["data"][label] = {
            "rate": round(rate * 100, 1),
            "year_1": year_1,
            "year_5": year_5,
        }

    return comparison

def get_insights(analysis: dict, decision_engine: dict, sip_engine: dict, growth: dict) -> dict:
    decision = decision_engine.get("decision", "NOT_READY")
    behavior = analysis.get("savings_behavior") or {}
    emergency = analysis.get("emergency") or {}
    
    trend = behavior.get("trend", "stable")
    volatility = behavior.get("volatility", 0.0)
    
    trend_text = f"Your savings are {trend}."
    vol_text = "Volatility is high." if volatility > 0.35 else "Volatility is low."
    behavior_insight = f"{trend_text} {vol_text}"
    
    if decision == "NOT_READY":
        st_summary = f"You are not ready to invest yet. Save ₹{emergency.get('remaining', 0):,.0f} more to start SIP safely."
        st_insight = f"At your current pace, you will be ready in ~{decision_engine.get('time_to_ready', 'a few months')}."
        st_action = "Focus entirely on building your emergency fund."
    elif decision == "PARTIAL":
        st_summary = "You have a partial safety net and can begin investing carefully."
        st_insight = "Investing 30% of savings builds the habit without risking your emergency fund progress."
        st_action = "Start your recommended small SIP now."
    else:
        st_summary = "You are fully prepared to maximize your investments."
        st_insight = "Your emergency fund is secure, allowing for aggressive long-term wealth growth."
        st_action = "Execute your recommended full SIP plan."

    rd_progress = emergency.get("progress_percent", 0.0)
    rd_target = emergency.get("target", 0.0)
    rd_summary = f"Your emergency fund is at {rd_progress:.0f}% of Rs.{rd_target:,.0f} target."
    rd_insight = f"It will take ~{decision_engine.get('time_to_ready', 'Unknown')} to reach your target." if emergency.get("remaining", 0) > 0 else "Your emergency fund target is complete."
    rd_action = f"You need Rs.{emergency.get('remaining', 0):,.0f} more to complete your emergency buffer." if emergency.get("remaining", 0) > 0 else "Maintain this buffer."

    pf_summary = "Your allocation is designed for your specific risk level."
    pf_insight = "Nifty 50 provides stability, Nifty 100 offers balance, and Midcap drives aggressive growth."
    pf_action = "Set up auto-invest for these allocations."

    sk_summary = "Direct stocks require more attention but offer higher potential returns."
    sk_insight = f"These suggestions align with your {sip_engine.get('risk_level', 'Low')} risk profile based on their volatility and trend."
    sk_action = "Use only a small satellite portion (10-15%) of your portfolio for direct stocks."

    gr_summary = "Compounding transforms consistent small habits into massive wealth over time."
    if growth.get("is_potential"):
        gr_insight = "Delaying your investments costs you significant potential gains."
        gr_action = "Focus on readiness so you can unlock these future returns."
    else:
        mod_profit = growth.get("data", {}).get("moderate", {}).get("year_5", {}).get("profit", 0)
        gr_insight = f"Your investments could generate ₹{mod_profit:,.0f} in pure profit over 5 years."
        gr_action = "Stay consistent with your monthly SIP to achieve these results."

    return {
        "overview": {
            "summary": "Your financial status indicates whether you are ready to invest.",
            "insight": behavior_insight,
            "action": decision_engine.get("next_step", "Keep saving."),
        },
        "readiness": {
            "summary": rd_summary,
            "insight": rd_insight,
            "action": rd_action,
        },
        "strategy": {
            "summary": st_summary,
            "insight": st_insight,
            "action": st_action,
        },
        "portfolio": {
            "summary": pf_summary,
            "insight": pf_insight,
            "action": pf_action,
        },
        "stocks": {
            "summary": sk_summary,
            "insight": sk_insight,
            "action": sk_action,
        },
        "growth": {
            "summary": gr_summary,
            "insight": gr_insight,
            "action": gr_action,
        }
    }


# =============================================================================
# UNIFIED PAYLOAD BUILDER
# =============================================================================

def build_live_investment_payload():
    """
    Purpose : Build the complete investment payload for the frontend.
    Input   : None (uses session user).
    Output  : Dictionary with investment plan, stocks, growth, and legacy fields.
    """
    user_id = config.get_current_user()["user_id"]

    # ── Single source of truth ──
    analysis = get_analysis_data(user_id)
    current = analysis.get("current") or {}
    behavior = analysis.get("savings_behavior") or {}
    emergency = analysis.get("emergency") or {}

    # ── Phase 3 & 4: Decision & SIP Engines ──
    decision_engine = get_decision_engine(analysis)
    sip_engine = get_sip_engine(analysis, decision_engine)
    alerts = get_alerts(analysis)
    what_if = get_what_if_analysis(analysis, sip_engine)

    # ── Phase 6: Enriched stocks ──
    stock_frame = load_stock_csv()
    stock_analysis, _ = analyze_stock_rows(stock_frame, generate_charts=False)
    
    risk_level = sip_engine.get("risk_level", "Low")
    
    recommended = filter_recommended_stocks(stock_analysis, risk_level)
    enriched_stocks = [_enrich_stock(s, risk_level) for s in recommended]

    # ── Phase 7: Growth comparison ──
    growth = build_growth_comparison(sip_engine)

    # ── Build legacy-compatible fields ──
    savings = current.get("savings", 0.0)
    savings_rate = current.get("savings_rate", 0.0)

    if savings <= 0:
        financial_status = "You are spending more than earning"
    elif savings_rate < 20:
        financial_status = "Low savings"
    else:
        financial_status = "Healthy financial condition"

    # Legacy advice list based on risk level
    if risk_level == "Low":
        advice = ["Build emergency fund", "Avoid high-risk investments"]
    elif risk_level in ["Moderate", "Medium"]:
        advice = ["Start SIP investments", "Balance risk and return"]
    else:
        advice = ["Invest in stocks", "Diversify portfolio"]

    # Legacy suggestion text
    if savings <= 0:
        suggestion = "You have no savings. Focus on reducing expenses."
    elif savings_rate < 20:
        suggestion = "Your savings are low. Build an emergency fund first."
    elif savings_rate < 40:
        suggestion = "You can start investing in mutual funds or SIP."
    else:
        suggestion = "You have strong savings. Consider stocks and diversified investments."

    insights = get_insights(analysis, decision_engine, sip_engine, growth)

    return {
        # ── Legacy fields (backward compatibility) ──
        "financial_status": financial_status,
        "investment_suggestion": suggestion,
        "risk_level": risk_level,
        "recommended_stocks": enriched_stocks,
        "advice": advice,

        # ── New Phase 3–7 fields ──
        "decision_engine": decision_engine,
        "sip_engine": sip_engine,
        "alerts": alerts,
        "what_if": what_if,
        "savings_behavior": behavior,
        "emergency": emergency,
        "growth": growth,
        "insights": insights,

        # ── Snapshot for quick display ──
        "snapshot": {
            "income": current.get("income", 0.0),
            "expense": current.get("expense", 0.0),
            "savings": current.get("savings", 0.0),
            "savings_rate": current.get("savings_rate", 0.0),
            "avg_savings": behavior.get("avg_savings", 0.0),
            "volatility": behavior.get("volatility", 0.0),
            "stable": behavior.get("stable", False),
        },
    }


# =============================================================================
# ROUTES
# =============================================================================

@investment_bp.route("/investment")
def investment():
    """
    Purpose : Renders the Investment page.
    Input   : None
    Output  : HTML template or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))

    return render_template(
        "user/investment.html",
        active_page="investment",
        user=config.get_current_user(),
    )


@investment_bp.route("/api/investment/data")
def api_investment_overview():
    """
    Purpose : Main investment API — returns the full investment payload.
    Input   : None (session user).
    Output  : JSON with plan, stocks, growth, emergency, and legacy fields.
    """
    if not config.is_logged_in():
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        return jsonify({
            "status": "success",
            "data": build_live_investment_payload(),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@investment_bp.route("/api/investment")
def api_investment_alias():
    """Compatibility alias for older clients expecting /api/investment."""
    return api_investment_overview()
