"""
goal_decision_engine.py
-----------------------
Purpose: Portfolio feasibility and conflict detection for multiple goals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_deadline(value: Any):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def detect_portfolio_conflicts(goals: List[Dict[str, Any]], allocation_result: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    conflicts: List[Dict[str, Any]] = []

    active_rows = [g for g in goals if str(g.get("status") or "active").lower() == "active"]
    if allocation_result.get("is_overloaded"):
        warnings.append("Active goals require more monthly savings than currently available.")

    # Identify deadline overlap by month bucket.
    month_bucket: Dict[str, int] = {}
    for row in active_rows:
        deadline = _parse_deadline(row.get("deadline"))
        if not deadline:
            continue
        key = deadline.strftime("%Y-%m")
        month_bucket[key] = month_bucket.get(key, 0) + 1

    overlapping = [k for k, v in month_bucket.items() if v > 1]
    if overlapping:
        warnings.append("Multiple active goals share the same deadline window.")
        for key in overlapping:
            conflicts.append(
                {
                    "type": "deadline_overlap",
                    "window": key,
                    "count": month_bucket[key],
                    "message": f"{month_bucket[key]} goals overlap in {key}.",
                }
            )

    allocations = allocation_result.get("allocations", {})
    for row in active_rows:
        goal_id = row.get("id")
        alloc = allocations.get(goal_id) or {}
        required = _coerce_float(alloc.get("required_monthly"))
        actual = _coerce_float(alloc.get("monthly_allocation"))
        if required > 0 and actual < required:
            name = row.get("goal_name") or f"Goal {goal_id}"
            conflicts.append(
                {
                    "type": "insufficient_allocation",
                    "goal_id": goal_id,
                    "goal_name": name,
                    "required_monthly": round(required, 2),
                    "allocated_monthly": round(actual, 2),
                    "message": f"{name} is underfunded for its deadline at the current allocation.",
                }
            )

    if not warnings and not conflicts:
        feasibility = "healthy"
    elif allocation_result.get("is_overloaded"):
        feasibility = "stressed"
    else:
        feasibility = "watch"

    return {
        "portfolio_feasibility": feasibility,
        "warnings": warnings,
        "conflicts": conflicts,
    }

