"""Web route blueprints for ADA modular web interface."""
from __future__ import annotations

from flask import Flask

from ada.interfaces.web.routes.core import core_bp
from ada.interfaces.web.routes.chat import chat_bp
from ada.interfaces.web.routes.models import models_bp
from ada.interfaces.web.routes.vault import vault_bp
from ada.interfaces.web.routes.health import health_bp
from ada.interfaces.web.routes.system import system_bp


def register_blueprints(app: Flask) -> None:
    """Register all modular route blueprints into the Flask application."""
    app.register_blueprint(core_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(vault_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(system_bp)
