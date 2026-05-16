"""SmartVest Flask app bootstrap.

Big picture:
- Load environment settings
- Set up Flask
- Initialize the database once at startup
- Register blueprints for each feature area
- Add shared security behavior such as CSRF protection

This file is intentionally small so the startup path is easy to follow.
"""
import logging
import secrets

logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
from flask import Flask, jsonify, request, session
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

import config
from modules.admin import admin_bp
from modules.analysis import analysis_bp, build_market_metrics, _cached_market_metrics
from modules.auth import auth_bp
from modules.expense import expense_bp
from modules.feedback import feedback_bp
from modules.income import income_bp
from modules.investment import investment_bp
from modules.review import review_bp
from modules.settings import settings_bp
from utils.cache import get_market_cache_version, init_cache
from utils.db import create_admin, init_db
from utils.mail import init_mail

load_dotenv()

logger = logging.getLogger("smartvest")


def _ensure_secret_key():
    """Return the required Flask secret key from the environment."""
    if not config.SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required.")
    return config.SECRET_KEY


def _csrf_exempt(path: str) -> bool:
    """Allow only login and signup to skip CSRF on first contact."""
    return (
        path.startswith("/api/auth/login")
        or path.startswith("/api/auth/signup")
        or path == "/login"
        or path == "/signup"
    )


def create_app():
    """Build and configure the Flask application object."""
    app = Flask(__name__)
    app.secret_key = _ensure_secret_key()
    # Keep local HTTP development working: browsers reject Secure cookies on plain localhost HTTP.
    session_cookie_secure = config.IS_PRODUCTION
    app.config.update(
        DEBUG=not config.IS_PRODUCTION,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=session_cookie_secure,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )
    logger.info("SmartVest startup environment: %s", config.ENVIRONMENT)
    logger.info("SmartVest active DB path: %s", config.DATABASE_PATH)
    logger.info("SmartVest upload base dir: %s", config.UPLOAD_BASE_DIR)
    logger.info("SmartVest static dir: %s", config.STATIC_DIR)
    init_mail(app)
    init_cache(app)

    # Why startup happens here:
    # We avoid import-time side effects and run DB bootstrap in one controlled place.
    init_db()
    try:
        admin_bootstrapped = create_admin()
        if admin_bootstrapped:
            logger.info("SmartVest admin bootstrap finished successfully.")
    except Exception:
        logger.exception("SmartVest admin bootstrap failed, but the app will continue to start.")

    app.register_blueprint(auth_bp)
    app.register_blueprint(expense_bp)
    app.register_blueprint(income_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(investment_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(review_bp)

    @app.before_request
    def enforce_csrf():
        # State-changing requests should prove they came from this browser session.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path.startswith("/api/"):
            if _csrf_exempt(request.path):
                return None
            token = session.get("csrf_token")
            header_token = request.headers.get("X-CSRF-Token")
            if not token or not header_token or token != header_token:
                return jsonify({"status": "error", "message": "Invalid CSRF token."}), 403
        return None

    @app.after_request
    def set_csrf_cookie(response):
        # The browser reads this cookie and sends the token back in X-CSRF-Token.
        if not session.get("csrf_token"):
            session["csrf_token"] = secrets.token_urlsafe(32)
        response.set_cookie(
            "XSRF-TOKEN",
            session["csrf_token"],
            httponly=False,
            secure=session_cookie_secure,
            samesite="Lax",
        )
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        # Keep internals out of the response while still logging the full trace server-side.
        logger.exception("Unhandled server error: %s", error)
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Unexpected server error."}), 500
        return "Unexpected server error.", 500

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(error):
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Uploaded file is too large."}), 413
        return "Uploaded file is too large.", 413

    @app.route("/api/admin/market-metrics")
    def api_admin_market_metrics():
        """Expose the admin market metrics endpoint from the app bootstrap."""
        if not config.is_admin():
            return jsonify({"status": "error", "message": "Forbidden."}), 403
        active_dataset = None
        try:
            from utils.market_data import get_active_dataset

            active_dataset = get_active_dataset()
        except Exception:
            active_dataset = None

        dataset_id = active_dataset["id"] if active_dataset else "no-dataset"
        return jsonify({
            "status": "success",
            "data": _cached_market_metrics(dataset_id, get_market_cache_version()),
        })

    return app


app = create_app()
if __name__ == "__main__":
    app.run(debug=not config.IS_PRODUCTION)
