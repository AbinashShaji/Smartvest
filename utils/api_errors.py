"""Centralized API error helpers for production-safe responses."""

import logging
from flask import jsonify

logger = logging.getLogger("smartvest.api")


def safe_api_error(error, *, status_code=500, message="Something went wrong. Please try again."):
    """
    Return a safe API error response without leaking internal exception details.

    Why this helper exists:
    - Raw exception strings can expose SQL, file paths, and runtime internals.
    - We still log full exception details server-side for debugging and incident response.
    """
    logger.exception("API exception: %s", error)
    return jsonify({"success": False, "status": "error", "message": message}), status_code
