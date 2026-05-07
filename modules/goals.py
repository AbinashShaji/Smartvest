"""
goals.py
--------
Compatibility adapter for the goals module.

This file keeps older imports working while delegating logic to the new
repository + analytics services.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.goal_analytics import (
    build_goal_analysis_context,
    build_goal_portfolio_payload,
    enrich_goal_row_with_context,
)
from modules.goal_repository import fetch_goal


def build_goal_analysis(user_id: Optional[int] = None, analysis_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Backward-compatible helper used by existing route code."""
    return build_goal_analysis_context(user_id=user_id, analysis_snapshot=analysis_snapshot)


def enrich_goal_row(goal_row: Dict[str, Any], analysis: Dict[str, Any], extra_saving: float = 0.0) -> Dict[str, Any]:
    """
    Backward-compatible row enrichment.
    `extra_saving` is currently ignored in the new architecture and reserved
    for future per-goal simulation routes.
    """
    return enrich_goal_row_with_context(goal_row, analysis, allocation_result=None)


def enrich_goal_rows(
    goal_rows: List[Dict[str, Any]],
    user_id: Optional[int] = None,
    analysis_snapshot: Optional[Dict[str, Any]] = None,
    extra_saving: float = 0.0,
) -> List[Dict[str, Any]]:
    """Backward-compatible bulk enrichment while preserving old signature."""
    payload = build_goal_portfolio_payload(goal_rows, user_id=user_id, analysis_snapshot=analysis_snapshot)
    return payload.get("goals", [])


def fetch_goal_by_id(user_id: int, goal_id: Any) -> Optional[Dict[str, Any]]:
    return fetch_goal(user_id, goal_id)

