"""Utilities for managing uploaded market datasets.

Big picture:
- save uploaded CSV files
- keep the latest datasets active
- remove stale DB rows and stale files together
"""

import logging
import os
from datetime import datetime

import pandas as pd
from werkzeug.utils import secure_filename

import config
from utils.db import get_db_connection


UPLOAD_DIR = os.path.join(config.UPLOAD_BASE_DIR, "market_data")
RETENTION_LIMIT = 3
STOCK_NAME_COLUMN = "stock_name"
REQUIRED_COLUMNS = [STOCK_NAME_COLUMN] + [f"day{i}" for i in range(1, 11)]
logger = logging.getLogger(__name__)


def ensure_upload_dir():
    """Create the market upload directory if it does not already exist."""
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
    """Read a market dataset and normalize the expected stock columns."""
    try:
        frame = pd.read_csv(dataset_path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return _normalize_stock_frame(frame)


def get_active_dataset():
    """Return the newest dataset currently marked active in SQLite."""
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
    """Return the latest dataset that is not the active one."""
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


def get_market_dataset_rows(limit=RETENTION_LIMIT):
    """Return the most recent market dataset records for admin views."""
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
    """Return a small preview so the admin UI can show the uploaded CSV safely."""
    frame = read_dataset_csv(dataset_path)
    if frame.empty:
        return []
    return frame.head(limit).fillna("").to_dict(orient="records")


def _safe_remove_dataset_file(dataset_path):
    """Remove a stored CSV if it still lives inside the market_data upload folder.

    We delete the file before removing the database row so storage cleanup and
    record cleanup stay in sync. Missing files are safe to ignore, but invalid
    paths are rejected so we never delete outside the upload directory.
    """
    if not dataset_path:
        return

    normalized_target = os.path.normpath(dataset_path)
    normalized_upload_dir = os.path.normpath(UPLOAD_DIR)
    try:
        common_root = os.path.commonpath([os.path.abspath(normalized_target), os.path.abspath(normalized_upload_dir)])
    except ValueError:
        logger.warning("Skipped dataset cleanup for invalid path: %s", dataset_path)
        return

    if common_root != os.path.abspath(normalized_upload_dir):
        logger.warning("Skipped dataset cleanup outside upload directory: %s", dataset_path)
        return

    if not os.path.exists(normalized_target):
        return

    try:
        os.remove(normalized_target)
    except OSError as exc:
        logger.warning("Failed to remove dataset file %s: %s", normalized_target, exc)


def _cleanup_untracked_dataset_files(kept_paths):
    """Remove CSV files from the upload folder that are no longer tracked in SQLite."""
    if not os.path.isdir(UPLOAD_DIR):
        return

    kept_real_paths = set()
    for path in kept_paths:
        if not path:
            continue
        try:
            kept_real_paths.add(os.path.realpath(path))
        except OSError:
            continue

    for entry in os.listdir(UPLOAD_DIR):
        if not entry.lower().endswith(".csv"):
            continue
        candidate = os.path.join(UPLOAD_DIR, entry)
        if os.path.realpath(candidate) in kept_real_paths:
            continue
        _safe_remove_dataset_file(candidate)


def _cleanup_old_datasets():
    """Keep only the newest allowed datasets and clean up their CSV files.

    Both the database row and the physical CSV must be removed so the storage
    directory does not accumulate orphan files after repeated uploads.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, dataset_path
        FROM market_datasets
        ORDER BY uploaded_at DESC, id DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    stale_rows = rows[RETENTION_LIMIT:]
    for stale in stale_rows:
        _safe_remove_dataset_file(stale.get("dataset_path") or "")
        cursor.execute("DELETE FROM market_datasets WHERE id = ?", (stale["id"],))
    conn.commit()

    # Sweep the upload folder too so stray CSVs from interrupted uploads do not linger.
    cursor.execute("""
        SELECT dataset_path
        FROM market_datasets
        ORDER BY uploaded_at DESC, id DESC
    """)
    kept_paths = [row["dataset_path"] for row in cursor.fetchall()]
    _cleanup_untracked_dataset_files(kept_paths)

    conn.commit()
    conn.close()


def save_uploaded_market_dataset(file_storage):
    """
    Save uploaded CSV, set it active, and return dataset metadata.

    Cleanup runs after the new dataset is recorded so the latest upload is
    always preserved while older datasets are trimmed from both the database
    and disk.
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
