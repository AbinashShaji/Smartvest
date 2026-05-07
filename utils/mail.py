"""
Mail helper for SmartVest contact messages.
Uses Flask-Mail with environment-based SMTP settings.
"""

import os
import re
from datetime import datetime

from flask import current_app
from flask_mail import Mail, Message


mail = Mail()
CONTACT_RECIPIENT = "fakermallu@gmail.com"


def init_mail(app):
    """
    Configure Flask-Mail from the current Flask app object.
    The app should already have environment variables loaded.
    """
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").strip().lower() in {"1", "true", "yes", "on"}
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "False").strip().lower() in {"1", "true", "yes", "on"}
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = re.sub(r"\s+", "", os.getenv("MAIL_PASSWORD", ""))
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"])
    app.config["MAIL_MAX_EMAILS"] = int(os.getenv("MAIL_MAX_EMAILS", "1"))
    app.config["MAIL_SUPPRESS_SEND"] = False
    mail.init_app(app)


def sanitize_text(value):
    """
    Keep normal text readable while stripping header-breaking characters.
    """
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def sanitize_message(value):
    """
    Preserve user message line breaks, but remove NUL characters and trim edges.
    """
    text = str(value or "").replace("\x00", "").strip()
    return text


def is_valid_email(value):
    """
    Lightweight email validation for the public contact form.
    """
    value = str(value or "").strip()
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value))


def send_contact_email(name, email, message):
    """
    Send a formatted SmartVest contact email through Gmail SMTP.
    """
    sender_name = sanitize_text(name)
    sender_email = sanitize_text(email)
    message_body = sanitize_message(message)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not sender_name or not sender_email or not message_body:
        raise ValueError("Missing contact form fields.")

    if len(sender_name) > 120 or len(sender_email) > 254 or len(message_body) > 4000:
        raise ValueError("One or more fields are too long.")

    if not is_valid_email(sender_email):
        raise ValueError("Please enter a valid email address.")

    mail_message = Message(
        subject=f"SmartVest Contact Form - {sender_name}",
        recipients=[CONTACT_RECIPIENT],
        reply_to=sender_email,
        sender=current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME"),
        body=(
            "New SmartVest contact form submission.\n\n"
            f"Sender Name: {sender_name}\n"
            f"Sender Email: {sender_email}\n"
            f"Timestamp: {timestamp}\n\n"
            "Message:\n"
            f"{message_body}\n"
        ),
    )

    mail.send(mail_message)

    return {
        "recipient": CONTACT_RECIPIENT,
        "timestamp": timestamp,
    }
