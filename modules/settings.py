from flask import Blueprint, render_template, redirect, url_for
import config

# Create the Settings Blueprint
# This module handles user profile views and preferences.
settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/settings")
def settings():
    """
    Purpose: Renders user profile control and account settings.
    Input: None (User data pulled from session)
    Output: HTML or Login redirect.
    """
    if not config.is_logged_in():
        return redirect(url_for('auth.login'))
    
    return render_template("user/settings.html", active_page="settings", user=config.get_current_user())
