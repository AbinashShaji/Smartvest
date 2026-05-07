"""
goal_analytics.py
-----------------
Purpose: Centralized goal analytics for row enrichment and portfolio summary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.analysis import get_analysis_data
from modules.goal_allocation_engine import allocate_monthly_savings
from modules.goal_decision_engine import detect_portfolio_conflicts


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_percent(saved: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return (saved / target) * 100.0


def _parse_date(value: Any):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _goal_type(goal_row: Dict[str, Any]) -> str:
    deadline = _parse_date(goal_row.get("deadline"))
    if deadline is not None:
        today = datetime.now()
        month_delta = (deadline.year - today.year) * 12 + (deadline.month - today.month)
        return "short" if month_delta <= 12 else "long"
    target = _coerce_float(goal_row.get("target_amount"))
    return "short" if target <= 5000 else "long"


def build_goal_analysis_context(user_id: Optional[int] = None, analysis_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    snapshot = analysis_snapshot if analysis_snapshot is not None else get_analysis_data(user_id)
    current = snapshot.get("current", {})
    yearly = snapshot.get("yearly", {})
    monthly_income = _coerce_float(current.get("income"))
    top_category = current.get("top_category")
    trend_data = list(yearly.get("trend_data") or current.get("trend_data") or [])

    savings_values: List[float] = []
    last_three_months: List[Dict[str, Any]] = []
    for item in trend_data[-3:]:
        expenses = _coerce_float(item.get("expense"))
        savings = monthly_income - expenses
        savings_values.append(savings)
        last_three_months.append(
            {
                "month": item.get("month"),
                "label": item.get("label") or item.get("month") or "",
                "expenses": round(expenses, 2),
                "savings": round(savings, 2),
            }
        )

    if savings_values:
        avg_savings = sum(savings_values) / len(savings_values)
        min_savings = min(savings_values)
        max_savings = max(savings_values)
    else:
        avg_savings = 0.0
        min_savings = 0.0
        max_savings = 0.0

    tip = (
        f"Reduce {top_category} spending to free up more money for goals."
        if top_category
        else "Track expense categories for targeted saving recommendations."
    )
    warning = ""
    if avg_savings <= 0:
        warning = "Average savings are non-positive, so timeline estimates are unstable."

    # Future integration hook:
    # Income -> Expenses -> Emergency Fund -> Goal Allocation -> Investment Residual
    emergency = snapshot.get("emergency", {}) or {}
    monthly_surplus = max(0.0, avg_savings)
    investment_residual = max(0.0, monthly_surplus)
    if emergency.get("remaining", 0.0) > 0 and emergency.get("progress_percent", 0.0) < 75:
        investment_residual = max(0.0, monthly_surplus * 0.4)

    return {
        "monthly_income": round(monthly_income, 2),
        "last_3_months": last_three_months,
        "avg_savings": round(avg_savings, 2),
        "min_savings": round(min_savings, 2),
        "max_savings": round(max_savings, 2),
        "top_category": top_category,
        "tip": tip,
        "warning": warning,
        "monthly_surplus": round(monthly_surplus, 2),
        "allocation_context": {
            "income": round(monthly_income, 2),
            "emergency": emergency,
            "goal_allocation_capacity": round(monthly_surplus, 2),
            "investment_residual_placeholder": round(investment_residual, 2),
        },
    }


def _estimate_months(remaining: float, monthly_amount: float):
    if remaining <= 0:
        return 0.0
    if monthly_amount <= 0:
        return None
    return remaining / monthly_amount


def enrich_goal_row_with_context(
    goal_row: Dict[str, Any],
    context: Dict[str, Any],
    allocation_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    target = _coerce_float(goal_row.get("target_amount"))
    saved = _coerce_float(goal_row.get("saved_amount"))
    remaining = max(0.0, target - saved)
    progress_percent = _safe_percent(saved, target)
    progress_bar = min(100.0, max(0.0, progress_percent))

    goal_id = goal_row.get("id")
    alloc = (allocation_result or {}).get("allocations", {}).get(goal_id, {})
    allocated_monthly = _coerce_float(alloc.get("monthly_allocation"))
    required_monthly = _coerce_float(alloc.get("required_monthly"))
    projected_months = alloc.get("projected_months")

    # Fallback to legacy-style estimates when allocation data is unavailable.
    if projected_months is None:
        avg_savings = _coerce_float(context.get("avg_savings"))
        min_savings = _coerce_float(context.get("min_savings"))
        max_savings = _coerce_float(context.get("max_savings"))
        best_months = _estimate_months(remaining, max_savings)
        real_months = _estimate_months(remaining, avg_savings)
        worst_months = _estimate_months(remaining, min_savings)
    else:
        real_months = projected_months
        if allocated_monthly > 0:
            best_months = _estimate_months(remaining, allocated_monthly * 1.2)
            worst_months = _estimate_months(remaining, max(0.01, allocated_monthly * 0.7))
        else:
            best_months = None
            worst_months = None

    if real_months is None:
        feasibility = "unrealistic"
        tone = "red"
    elif real_months > 24:
        feasibility = "risky"
        tone = "yellow"
    else:
        feasibility = "feasible"
        tone = "green"

    warning = context.get("warning") or ""
    if real_months is not None and real_months > 24:
        warning = "This goal may take more than 24 months at the current portfolio allocation."
    if required_monthly > 0 and allocated_monthly > 0 and allocated_monthly < required_monthly:
        warning = "Current monthly allocation is below the deadline-required pace."

    insight = f"Reach in ~{real_months:.2f} mo" if real_months is not None else "No clear timeline yet"

    return {
        **goal_row,
        "goal_type": _goal_type(goal_row),
        "target_amount": round(target, 2),
        "saved_amount": round(saved, 2),
        "remaining_amount": round(remaining, 2),
        "progress_percent": round(progress_percent, 2),
        "progress_bar": round(progress_bar, 2),
        "analysis": {
            "best_months": best_months,
            "realistic_months": real_months,
            "worst_months": worst_months,
            "feasibility": feasibility,
            "tone": tone,
            "insight": insight,
            "warning": warning,
            "tip": context.get("tip", ""),
            "allocated_monthly": round(allocated_monthly, 2),
            "required_monthly": round(required_monthly, 2),
        },
        "smart_analysis": {
            "monthly_income": context.get("monthly_income", 0.0),
            "last_3_months": context.get("last_3_months", []),
            "avg_savings": context.get("avg_savings", 0.0),
            "min_savings": context.get("min_savings", 0.0),
            "max_savings": context.get("max_savings", 0.0),
            "top_category": context.get("top_category"),
            "tip": context.get("tip", ""),
            "warning": warning,
            "allocation_context": context.get("allocation_context", {}),
        },
        "time_estimates": {
            "best_months": best_months,
            "real_months": real_months,
            "worst_months": worst_months,
            "best_months_display": best_months,
            "real_months_display": real_months,
            "worst_months_display": worst_months,
        },
        "feasibility": {
            "label": feasibility.title(),
            "tone": tone,
        },
        "tip": context.get("tip", ""),
        "warning": warning,
    }


def build_goal_portfolio_summary(goals: List[Dict[str, Any]], allocation_result: Dict[str, Any], decision_result: Dict[str, Any]) -> Dict[str, Any]:
    total_goals = len(goals)
    active_goals = [g for g in goals if str(g.get("status") or "active").lower() == "active"]
    paused_goals = [g for g in goals if str(g.get("status") or "").lower() == "paused"]
    completed_goals = [g for g in goals if str(g.get("status") or "").lower() == "completed"]
    archived_goals = [g for g in goals if str(g.get("status") or "").lower() == "archived"]

    total_target = sum(_coerce_float(g.get("target_amount")) for g in goals)
    total_saved = sum(_coerce_float(g.get("saved_amount")) for g in goals)
    total_remaining = max(0.0, total_target - total_saved)

    if total_target > 0:
        avg_progress = (total_saved / total_target) * 100.0
    else:
        avg_progress = 0.0

    return {
        "total_goals": total_goals,
        "active_goals": len(active_goals),
        "paused_goals": len(paused_goals),
        "completed_goals": len(completed_goals),
        "archived_goals": len(archived_goals),
        "total_target": round(total_target, 2),
        "total_saved": round(total_saved, 2),
        "total_remaining": round(total_remaining, 2),
        "avg_progress": round(avg_progress, 2),
        "required_monthly_savings": allocation_result.get("required_monthly_savings", 0.0),
        "available_monthly_savings": allocation_result.get("available_monthly_savings", 0.0),
        "portfolio_feasibility": decision_result.get("portfolio_feasibility", "healthy"),
        "warnings": decision_result.get("warnings", []),
        "conflicts": decision_result.get("conflicts", []),
    }


def build_goal_portfolio_payload(goals: List[Dict[str, Any]], user_id: Optional[int] = None, analysis_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = build_goal_analysis_context(user_id=user_id, analysis_snapshot=analysis_snapshot)
    allocation = allocate_monthly_savings(goals, context.get("monthly_surplus", 0.0))
    decision = detect_portfolio_conflicts(goals, allocation)
    enriched = [enrich_goal_row_with_context(row, context, allocation_result=allocation) for row in goals]
    summary = build_goal_portfolio_summary(goals, allocation, decision)

    return {
        "goals": enriched,
        "portfolio_summary": summary,
        "allocation": allocation,
        "decision": decision,
        "analysis_context": context,
    }

