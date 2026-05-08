"""SmartVest Flask app bootstrap with production-safe startup flow."""
import logging
import secrets

from dotenv import load_dotenv
from flask import Flask, jsonify, request, session

import config
from modules.admin import admin_bp
from modules.analysis import analysis_bp, build_market_metrics
from modules.auth import auth_bp
from modules.expense import expense_bp
from modules.feedback import feedback_bp
from modules.income import income_bp
from modules.investment import investment_bp
from modules.review import review_bp
from modules.settings import settings_bp
from utils.db import create_admin, init_db
from utils.mail import init_mail

load_dotenv()

logger = logging.getLogger("smartvest")
logging.basicConfig(level=logging.INFO)


def _ensure_secret_key():
    if not config.SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required.")
    return config.SECRET_KEY


def _csrf_exempt(path: str) -> bool:
    return path.startswith("/api/auth/login") or path.startswith("/api/auth/signup")


def create_app():
    app = Flask(__name__)
    app.secret_key = _ensure_secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.IS_PRODUCTION,
    )
    init_mail(app)

    # Why startup happens here:
    # We avoid import-time side effects and run DB bootstrap in one controlled place.
    init_db()
    create_admin()

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
        # Why this exists:
        # Any state-changing endpoint must include an anti-CSRF token header.
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
        if not session.get("csrf_token"):
            session["csrf_token"] = secrets.token_urlsafe(32)
        response.set_cookie(
            "XSRF-TOKEN",
            session["csrf_token"],
            httponly=False,
            secure=config.IS_PRODUCTION,
            samesite="Lax",
        )
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        logger.exception("Unhandled server error: %s", error)
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Unexpected server error."}), 500
        return "Unexpected server error.", 500

    @app.route("/api/admin/market-metrics")
    def api_admin_market_metrics():
        if not config.is_admin():
            return jsonify({"status": "error", "message": "Forbidden."}), 403
        return jsonify({"status": "success", "data": build_market_metrics()})

    return app


app = create_app()
