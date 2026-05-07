"""
goal_allocation_engine.py
-------------------------
Purpose: Portfolio-aware monthly savings allocation for active goals.
Design : Distribute one shared monthly savings pool across many goals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


PRIORITY_WEIGHT = {
    "critical": 4.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _months_to_deadline(deadline: Any) -> int | None:
    if not deadline:
        return None
    try:
        parsed = datetime.strptime(str(deadline), "%Y-%m-%d")
    except ValueError:
        return None
    today = datetime.now()
    month_delta = (parsed.year - today.year) * 12 + (parsed.month - today.month)
    return max(1, month_delta)


def allocate_monthly_savings(goals: List[Dict[str, Any]], monthly_savings: float) -> Dict[str, Any]:
    """
    Returns per-goal allocations and projection metadata.
    """
    pool = max(0.0, _coerce_float(monthly_savings))
    active_goals = []
    for row in goals:
        status = str(row.get("status") or "active").lower()
        if status != "active":
            continue
        target = _coerce_float(row.get("target_amount"))
        saved = _coerce_float(row.get("saved_amount"))
        remaining = max(0.0, target - saved)
        if remaining <= 0:
            continue
        priority = str(row.get("priority") or "medium").lower()
        if priority not in PRIORITY_WEIGHT:
            priority = "medium"
        months_left = _months_to_deadline(row.get("deadline"))
        required = (remaining / months_left) if months_left else 0.0
        urgency_multiplier = 1.0
        if months_left is not None and months_left <= 6:
            urgency_multiplier = 1.5
        elif months_left is not None and months_left <= 12:
            urgency_multiplier = 1.2
        score = PRIORITY_WEIGHT[priority] * urgency_multiplier
        active_goals.append(
            {
                "id": row.get("id"),
                "remaining": remaining,
                "priority": priority,
                "months_left": months_left,
                "required_monthly": required,
                "score": score,
            }
        )

    if not active_goals:
        return {
            "available_monthly_savings": round(pool, 2),
            "required_monthly_savings": 0.0,
            "allocation_load_ratio": 0.0,
            "is_overloaded": False,
            "allocations": {},
        }

    required_total = sum(item["required_monthly"] for item in active_goals if item["required_monthly"] > 0)
    is_overloaded = pool < required_total if required_total > 0 else False
    score_total = sum(item["score"] for item in active_goals) or 1.0

    allocations: Dict[Any, Dict[str, Any]] = {}
    if pool <= 0:
        for item in active_goals:
            allocations[item["id"]] = {
                "monthly_allocation": 0.0,
                "required_monthly": round(item["required_monthly"], 2),
                "projected_months": None,
            }
    elif required_total > 0 and pool >= required_total:
        # Enough capacity: satisfy required monthly for each deadline-driven goal.
        weighted_total = score_total
        for item in active_goals:
            allocation = item["required_monthly"] if item["required_monthly"] > 0 else 0.0
            if allocation <= 0:
                # No deadline -> allocate small weighted baseline from spare capacity.
                allocation = pool * (item["score"] / weighted_total) * 0.15
            projected = item["remaining"] / allocation if allocation > 0 else None
            allocations[item["id"]] = {
                "monthly_allocation": round(allocation, 2),
                "required_monthly": round(item["required_monthly"], 2),
                "projected_months": round(projected, 2) if projected is not None else None,
            }
    else:
        # Not enough capacity: weighted distribution by priority + urgency.
        for item in active_goals:
            allocation = pool * (item["score"] / score_total)
            projected = item["remaining"] / allocation if allocation > 0 else None
            allocations[item["id"]] = {
                "monthly_allocation": round(allocation, 2),
                "required_monthly": round(item["required_monthly"], 2),
                "projected_months": round(projected, 2) if projected is not None else None,
            }

    return {
        "available_monthly_savings": round(pool, 2),
        "required_monthly_savings": round(required_total, 2),
        "allocation_load_ratio": round((required_total / pool), 4) if pool > 0 else 0.0,
        "is_overloaded": is_overloaded,
        "allocations": allocations,
    }
