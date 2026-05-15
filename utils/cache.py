"""Central cache helpers for SmartVest.

This module keeps caching lightweight and process-local via Flask-Caching's
SimpleCache backend, which is a safe fit for PythonAnywhere and SQLite.
"""

from __future__ import annotations

import logging
from typing import Optional

from flask_caching import Cache


logger = logging.getLogger("smartvest.cache")
cache = Cache()

_DEFAULT_TIMEOUT_SECONDS = 60
_VERSION_TIMEOUT_SECONDS = 60 * 60 * 24 * 7


def init_cache(app):
    """Initialize Flask-Caching with a small in-memory SimpleCache backend."""
    app.config.setdefault("CACHE_TYPE", "SimpleCache")
    app.config.setdefault("CACHE_DEFAULT_TIMEOUT", _DEFAULT_TIMEOUT_SECONDS)
    app.config.setdefault("CACHE_THRESHOLD", 256)
    cache.init_app(app)
    logger.info("SmartVest cache initialized with SimpleCache.")


def _version_key(namespace: str, identifier: Optional[object] = None) -> str:
    if identifier is None:
        return f"smartvest:cache-version:{namespace}"
    return f"smartvest:cache-version:{namespace}:{identifier}"


def get_cache_version(namespace: str, identifier: Optional[object] = None) -> int:
    """Return the current version for a cache namespace."""
    key = _version_key(namespace, identifier)
    version = cache.get(key)
    if version is None:
        version = 1
        cache.set(key, version, timeout=_VERSION_TIMEOUT_SECONDS)
    return int(version)


def bump_cache_version(namespace: str, identifier: Optional[object] = None) -> int:
    """Advance the version token for a cache namespace."""
    key = _version_key(namespace, identifier)
    version = get_cache_version(namespace, identifier) + 1
    cache.set(key, version, timeout=_VERSION_TIMEOUT_SECONDS)
    return version


def get_user_analysis_version(user_id: int) -> int:
    return get_cache_version("analysis-user", user_id)


def bump_user_analysis_version(user_id: int) -> int:
    return bump_cache_version("analysis-user", user_id)


def get_analysis_global_version() -> int:
    return get_cache_version("analysis-global")


def bump_analysis_global_version() -> int:
    return bump_cache_version("analysis-global")


def get_admin_cache_version() -> int:
    return get_cache_version("admin")


def bump_admin_cache_version() -> int:
    return bump_cache_version("admin")


def get_market_cache_version() -> int:
    return get_cache_version("market")


def bump_market_cache_version() -> int:
    return bump_cache_version("market")
