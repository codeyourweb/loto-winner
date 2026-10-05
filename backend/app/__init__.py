"""Flask application "Loto Winner".

The hardening applied here follows the OWASP recommendations:

* A05:2021 Security Misconfiguration — explicit configuration, generic errors,
  security headers, masked server;
* A03:2021 Injection — strict upstream validation, parameterised SQL queries;
* A07:2021 Identification and Authentication Failures — hardened cookies;
* API4:2023 Unrestricted Resource Consumption — bounded body size and rate.
"""

from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .db import init_app as init_db_app
from .extensions import limiter
from .routes import api
from .security import apply_security_headers


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Explicit errors ------------------------------------------------------
    # In production, no trace may leak to the client.
    if not app.config.get("TESTING"):
        app.config.setdefault("PROPAGATE_EXCEPTIONS", False)

    # --- CORS: origin allowlist (never "*" when unconfigured) -----------------
    origins = app.config.get("CORS_ORIGINS") or []
    if origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": origins}},
            methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            max_age=600,
        )

    # --- Rate limiting --------------------------------------------------------
    limiter.init_app(app)

    init_db_app(app)
    app.register_blueprint(api)

    # --- Security headers on EVERY response -----------------------------------
    @app.after_request
    def _security_headers(response):
        return apply_security_headers(
            response, hsts=bool(app.config.get("SECURITY_HSTS"))
        )

    # --- Error handlers: generic messages, no leakage -------------------------
    @app.errorhandler(400)
    def bad_request(_error):
        return jsonify(error="Requête invalide."), 400

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Ressource introuvable."), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Méthode non autorisée."), 405

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify(error="Corps de requête trop volumineux."), 413

    @app.errorhandler(429)
    def too_many_requests(_error):
        return jsonify(error="Trop de requêtes. Réessayez dans un instant."), 429

    @app.errorhandler(500)
    def internal_error(_error):
        # No technical detail is returned to the client.
        return jsonify(error="Erreur interne du serveur."), 500

    @app.route("/")
    def index():
        return jsonify(
            name="Loto Winner API",
            version="1.0.0",
            endpoints=[
                "/api/health",
                "/api/config",
                "/api/draws",
                "/api/jackpots",
                "/api/stats/hot-numbers",
                "/api/simulate",
                "/api/simulations",
            ],
        )

    return app
