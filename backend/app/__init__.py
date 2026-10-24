import os
from typing import Optional, Dict, Any
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .config import config_by_name, Config
from .db.session import init_db, close_session, SessionScoped
from .db.models import AgentModel
from .api.routes import api_bp


def seed_default_agents():
    """Seed default vulnerable and hardened demo agents if not present."""
    session = SessionScoped()
    demo_agents = [
        {
            "id": "vulnerable-demo",
            "name": "Vulnerable Demo Agent",
            "adapter_type": "mock",
            "config": {"mode": "vulnerable"},
            "description": "Demonstration agent vulnerable to prompt injection, secret leakage, and tool abuse.",
        },
        {
            "id": "hardened-demo",
            "name": "Hardened Demo Agent",
            "adapter_type": "mock",
            "config": {"mode": "hardened"},
            "description": "Hardened demonstration agent that enforces policy guardrails and tool authorization.",
        },
    ]
    for d in demo_agents:
        if not session.query(AgentModel).filter_by(id=d["id"]).first():
            session.add(AgentModel(
                id=d["id"],
                name=d["name"],
                adapter_type=d["adapter_type"],
                config=d["config"],
                description=d["description"],
                enabled=True,
            ))
    try:
        session.commit()
    except Exception:
        session.rollback()


def create_app(config_name: Optional[str] = None, config_override: Optional[Dict[str, Any]] = None) -> Flask:
    """
    Application factory for Faultline backend.
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()

    app = Flask(__name__)
    config_cls = config_by_name.get(config_name, Config)
    app.config.from_object(config_cls)

    if config_override:
        app.config.update(config_override)

    # Configure CORS with explicit allowed origins
    allowed_origins = app.config.get("CORS_ALLOWED_ORIGINS", ["http://localhost:5173", "http://localhost:3000"])
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

    # Initialize Database
    init_db(app.config["DATABASE_URL"])
    seed_default_agents()

    # Register session teardown
    app.teardown_appcontext(close_session)

    # Register Blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

    @app.get("/")
    @app.get("/report")
    def frontend_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/assets/<path:filename>")
    def frontend_assets(filename):
        return send_from_directory(frontend_dir, filename)

    # Error Handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource Not Found", "message": str(error)}), 404

    @app.errorhandler(422)
    def unprocessable(error):
        return jsonify({"error": "Unprocessable Entity", "message": str(error)}), 422

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal Server Error"}), 500

    return app
