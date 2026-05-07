"""
Utilities for managing uploaded market datasets.
This module is the single source of truth for stock CSV file paths.
"""

import os
from datetime import datetime

import pandas as pd
from werkzeug.utils import secure_filename

from utils.db import get_db_connection


UPLOAD_DIR = os.path.join("uploads", "market_data")
STOCK_NAME_COLUMN = "stock_name"
REQUIRED_COLUMNS = [STOCK_NAME_COLUMN] + [f"day{i}" for i in range(1, 11)]


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _normalize_stock_frame(df):
    normalized = df.copy()
    if STOCK_NAME_COLUMN not in normalized.columns:
        if "name" in normalized.columns:
            normalized[STOCK_NAME_COLUMN] = normalized["name"]
        else:
            normalized[STOCK_NAME_COLUMN] = ""
    if "name" not in normalized.columns:
        normalized["name"] = normalized[STOCK_NAME_COLUMN]
    for column in REQUIRED_COLUMNS[1:]:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    return normalized.reindex(columns=[STOCK_NAME_COLUMN, "name"] + REQUIRED_COLUMNS[1:])


def read_dataset_csv(dataset_path):
    try:
        frame = pd.read_csv(dataset_path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return _normalize_stock_frame(frame)


def get_active_dataset():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, dataset_path, uploaded_at, total_records, is_active
        FROM market_datasets
        WHERE is_active = 1
        ORDER BY uploaded_at DESC, id DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_previous_dataset(active_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, dataset_path, uploaded_at, total_records, is_active
        FROM market_datasets
        WHERE id != ?
        ORDER BY uploaded_at DESC, id DESC
        LIMIT 1
    """, (active_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_market_dataset_rows(limit=3):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, dataset_path, uploaded_at, total_records, is_active
        FROM market_datasets
        ORDER BY uploaded_at DESC, id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_dataset_preview(dataset_path, limit=8):
    frame = read_dataset_csv(dataset_path)
    if frame.empty:
        return []
    return frame.head(limit).fillna("").to_dict(orient="records")


def _cleanup_old_datasets():
    """
    Keep only latest 3 uploaded datasets and remove stale files from disk.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, dataset_path
        FROM market_datasets
        ORDER BY uploaded_at DESC, id DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    stale_rows = rows[3:]
    for stale in stale_rows:
        stale_path = stale.get("dataset_path") or ""
        if stale_path and os.path.exists(stale_path):
            try:
                os.remove(stale_path)
            except OSError:
                pass
        cursor.execute("DELETE FROM market_datasets WHERE id = ?", (stale["id"],))
    conn.commit()
    conn.close()


def save_uploaded_market_dataset(file_storage):
    """
    Save uploaded CSV, set it active, and return dataset metadata.
    """
    ensure_upload_dir()
    original_name = secure_filename(file_storage.filename or "")
    if not original_name.lower().endswith(".csv"):
        raise ValueError("Only CSV files are allowed.")

    stamped_name = f"{int(datetime.now().timestamp())}_{original_name}"
    dataset_path = os.path.join(UPLOAD_DIR, stamped_name)
    file_storage.save(dataset_path)

    frame = read_dataset_csv(dataset_path)
    total_records = len(frame.index)
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE market_datasets SET is_active = 0")
    cursor.execute("""
        INSERT INTO market_datasets (filename, dataset_path, uploaded_at, total_records, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (original_name, dataset_path, uploaded_at, total_records))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    _cleanup_old_datasets()
    active = get_active_dataset()
    if active and active.get("id") == new_id:
        return active
    return {
        "id": new_id,
        "filename": original_name,
        "dataset_path": dataset_path,
        "uploaded_at": uploaded_at,
        "total_records": total_records,
        "is_active": 1,
    }
