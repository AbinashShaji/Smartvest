"""
goal_repository.py
------------------
Purpose: Centralized database access for goals.
Design : Keep SQL out of route handlers and provide migration-safe reads/writes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.db import get_db_connection


VALID_STATUSES = {"active", "paused", "completed", "archived"}
VALID_PRIORITIES = {"critical", "high", "medium", "low"}


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_status(value: Any, default: str = "active") -> str:
    normalized = str(value or default).strip().lower()
    return normalized if normalized in VALID_STATUSES else default


def _normalize_priority(value: Any, default: str = "medium") -> str:
    normalized = str(value or default).strip().lower()
    return normalized if normalized in VALID_PRIORITIES else default


def fetch_user_goals(user_id: int, include_archived: bool = False) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_archived:
        cursor.execute("SELECT * FROM goals WHERE user_id = ? ORDER BY id DESC", (user_id,))
    else:
        cursor.execute(
            "SELECT * FROM goals WHERE user_id = ? AND COALESCE(status, 'active') != 'archived' ORDER BY id DESC",
            (user_id,),
        )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def fetch_goal(user_id: int, goal_id: Any) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row is not None else None


def create_goal(
    user_id: int,
    name: str,
    target_amount: float,
    saved_amount: float,
    deadline: str,
    status: str = "active",
    priority: str = "medium",
) -> Dict[str, Any]:
    status_value = _normalize_status(status, default="active")
    priority_value = _normalize_priority(priority, default="medium")
    now = _now_iso()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO goals (
            user_id, goal_name, target_amount, saved_amount, deadline,
            status, priority, created_at, updated_at, paused_at, completed_at, archived_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            name,
            target_amount,
            saved_amount,
            deadline,
            status_value,
            priority_value,
            now,
            now,
            None,
            None,
            None,
        ),
    )
    conn.commit()
    goal_id = cursor.lastrowid
    cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
    row = dict(cursor.fetchone())
    conn.close()
    return row


def update_goal(
    user_id: int,
    goal_id: Any,
    name: str,
    target_amount: float,
    saved_amount: float,
    deadline: str,
    priority: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = _now_iso()
    current = fetch_goal(user_id, goal_id)
    if current is None:
        return None

    priority_value = _normalize_priority(priority or current.get("priority"), default="medium")
    status_value = _normalize_status(current.get("status"), default="active")

    # Auto-complete when saved amount reaches or exceeds target.
    completed_at = current.get("completed_at")
    if target_amount > 0 and saved_amount >= target_amount and status_value != "archived":
        status_value = "completed"
        completed_at = completed_at or now
    elif status_value == "completed" and saved_amount < target_amount:
        status_value = "active"
        completed_at = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE goals
        SET goal_name = ?, target_amount = ?, saved_amount = ?, deadline = ?,
            status = ?, priority = ?, updated_at = ?, completed_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            name,
            target_amount,
            saved_amount,
            deadline,
            status_value,
            priority_value,
            now,
            completed_at,
            goal_id,
            user_id,
        ),
    )
    conn.commit()
    cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row is not None else None


def transition_goal_status(user_id: int, goal_id: Any, target_status: str) -> Optional[Dict[str, Any]]:
    status_value = _normalize_status(target_status, default="active")
    now = _now_iso()
    current = fetch_goal(user_id, goal_id)
    if current is None:
        return None

    paused_at = current.get("paused_at")
    completed_at = current.get("completed_at")
    archived_at = current.get("archived_at")

    if status_value == "paused":
        paused_at = paused_at or now
    if status_value == "completed":
        completed_at = completed_at or now
    if status_value == "archived":
        archived_at = archived_at or now

    if status_value == "active":
        paused_at = None
        if current.get("saved_amount", 0) < current.get("target_amount", 0):
            completed_at = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE goals
        SET status = ?, paused_at = ?, completed_at = ?, archived_at = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (status_value, paused_at, completed_at, archived_at, now, goal_id, user_id),
    )
    conn.commit()
    cursor.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row is not None else None


def soft_archive_goal(user_id: int, goal_id: Any) -> bool:
    row = transition_goal_status(user_id, goal_id, "archived")
    return row is not None
