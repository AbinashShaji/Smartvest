"""
goals.py
--------
Purpose : Goal analysis helpers used by the existing expense blueprint.
          These helpers only extend the current goal flow; they do not change
          the database schema or existing routes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.db import get_db_connection


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Convert values from SQLite or JSON into safe floats."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_percent(saved: float, target: float) -> float:
    """Return a progress percentage without dividing by zero."""
    if target <= 0:
        return 0.0
    return (saved / target) * 100.0


def _parse_date(value: Any) -> Optional[datetime]:
    """Parse goal or expense dates without raising on invalid input."""
    if not value:
        return None

    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """Shift a year/month pair by a month offset."""
    total_months = year * 12 + (month - 1) + offset
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    return new_year, new_month


def _month_key(value: datetime) -> str:
    """Build a YYYY-MM key for monthly grouping."""
    return f"{value.year:04d}-{value.month:02d}"


def _month_label(value: str) -> str:
    """Convert a YYYY-MM key into a readable label."""
    try:
        parsed = datetime.strptime(value + "-01", "%Y-%m-%d")
        return parsed.strftime("%b %Y")
    except ValueError:
        return value


def _goal_type(goal_row: Dict[str, Any]) -> str:
    """
    Derive a short/long label without persisting a new schema column.
    Deadline takes priority; otherwise target size is used as a fallback.
    """
    deadline = _parse_date(goal_row.get("deadline"))
    if deadline is not None:
        today = datetime.now()
        month_delta = (deadline.year - today.year) * 12 + (deadline.month - today.month)
        return "short" if month_delta <= 12 else "long"

    target = _coerce_float(goal_row.get("target_amount"))
    return "short" if target <= 5000 else "long"


def build_goal_analysis(user_id: int) -> Dict[str, Any]:
    """
    Build a safe goal analysis snapshot from live expense and income data.
    The values are computed from the most recent three months of savings.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount, category, date FROM expenses WHERE user_id = ?",
        (user_id,),
    )
    expense_rows = [dict(row) for row in cursor.fetchall()]

    cursor.execute(
        "SELECT amount FROM income WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    income_row = cursor.fetchone()
    monthly_income = _coerce_float(income_row["amount"]) if income_row is not None else 0.0
    conn.close()

    expense_totals_by_category: Dict[str, float] = {}
    monthly_expenses: Dict[str, float] = {}

    for row in expense_rows:
        amount = _coerce_float(row.get("amount"))
        category = str(row.get("category") or "Other").strip() or "Other"
        expense_totals_by_category[category] = expense_totals_by_category.get(category, 0.0) + amount

        parsed_date = _parse_date(row.get("date"))
        if parsed_date is None:
            continue

        month_key = _month_key(parsed_date)
        monthly_expenses[month_key] = monthly_expenses.get(month_key, 0.0) + amount

    today = datetime.now()
    month_keys: List[str] = []
    month_labels: List[str] = []
    for offset in (-2, -1, 0):
        year, month = _shift_month(today.year, today.month, offset)
        key = f"{year:04d}-{month:02d}"
        month_keys.append(key)
        month_labels.append(_month_label(key))

    last_three_months: List[Dict[str, Any]] = []
    savings_values: List[float] = []
    for key, label in zip(month_keys, month_labels):
        expenses = monthly_expenses.get(key, 0.0)
        savings = monthly_income - expenses
        savings_values.append(savings)
        last_three_months.append(
            {
                "month": key,
                "label": label,
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

    top_category = None
    if expense_totals_by_category:
        top_category = max(expense_totals_by_category.items(), key=lambda item: item[1])[0]

    if top_category:
        tip = f"Reduce {top_category} spending to free up more money for this goal."
    else:
        tip = "Track expense categories for a more targeted saving tip."

    warning = ""
    if avg_savings <= 0:
        warning = "Average savings are non-positive, so time estimates are unrealistic."

    return {
        "monthly_income": round(monthly_income, 2),
        "last_3_months": last_three_months,
        "avg_savings": round(avg_savings, 2),
        "min_savings": round(min_savings, 2),
        "max_savings": round(max_savings, 2),
        "top_category": top_category,
        "tip": tip,
        "warning": warning,
    }


def _estimate_months(remaining: float, monthly_savings: float) -> Optional[float]:
    """Estimate time in months, returning None when it cannot be computed."""
    if remaining <= 0:
        return 0.0
    if monthly_savings <= 0:
        return None
    return remaining / monthly_savings


def enrich_goal_row(goal_row: Dict[str, Any], analysis: Dict[str, Any], extra_saving: float = 0.0) -> Dict[str, Any]:
    """
    Extend a goal row with progress, time estimates, feasibility, and insight
    fields used by the updated goals page.
    """
    target = _coerce_float(goal_row.get("target_amount"))
    saved = _coerce_float(goal_row.get("saved_amount"))
    remaining = max(0.0, target - saved)
    progress_percent = _safe_percent(saved, target)
    progress_bar = min(100.0, max(0.0, progress_percent))

    effective_avg = _coerce_float(analysis.get("avg_savings")) + max(0.0, _coerce_float(extra_saving))
    effective_min = _coerce_float(analysis.get("min_savings")) + max(0.0, _coerce_float(extra_saving))
    effective_max = _coerce_float(analysis.get("max_savings")) + max(0.0, _coerce_float(extra_saving))

    best_months = _estimate_months(remaining, effective_max)
    real_months = _estimate_months(remaining, effective_avg)
    worst_months = _estimate_months(remaining, effective_min)

    if effective_avg <= 0:
        feasibility = "Unrealistic"
        feasibility_tone = "red"
    elif real_months is not None and real_months > 24:
        feasibility = "Risky"
        feasibility_tone = "yellow"
    else:
        feasibility = "Feasible"
        feasibility_tone = "green"

    warning = analysis.get("warning") or ""
    if effective_avg > 0 and real_months is not None and real_months > 24:
        warning = "This goal may take more than 24 months at the current saving rate."

    return {
        **goal_row,
        "goal_type": _goal_type(goal_row),
        "target_amount": round(target, 2),
        "saved_amount": round(saved, 2),
        "remaining_amount": round(remaining, 2),
        "progress_percent": round(progress_percent, 2),
        "progress_bar": round(progress_bar, 2),
        "smart_analysis": {
            "monthly_income": analysis.get("monthly_income", 0.0),
            "last_3_months": analysis.get("last_3_months", []),
            "avg_savings": analysis.get("avg_savings", 0.0),
            "min_savings": analysis.get("min_savings", 0.0),
            "max_savings": analysis.get("max_savings", 0.0),
            "top_category": analysis.get("top_category"),
            "tip": analysis.get("tip", ""),
            "warning": warning,
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
            "label": feasibility,
            "tone": feasibility_tone,
        },
        "tip": analysis.get("tip", ""),
        "warning": warning,
    }


def enrich_goal_rows(goal_rows: List[Dict[str, Any]], user_id: int, extra_saving: float = 0.0) -> List[Dict[str, Any]]:
    """Load shared analysis once and enrich each goal row in a single pass."""
    analysis = build_goal_analysis(user_id)
    return [enrich_goal_row(goal_row, analysis, extra_saving=extra_saving) for goal_row in goal_rows]


def fetch_goal_by_id(user_id: int, goal_id: Any) -> Optional[Dict[str, Any]]:
    """Read back a single goal row for the current user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row is not None else None

