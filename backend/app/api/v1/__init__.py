from flask import Blueprint
from .agents import agents_bp
from .tests import tests_bp
from .runs import runs_bp
from .reports import reports_bp
from .health import health_bp

v1_bp = Blueprint("v1", __name__)

v1_bp.register_blueprint(agents_bp, url_prefix="/agents")
v1_bp.register_blueprint(tests_bp, url_prefix="/tests")
v1_bp.register_blueprint(runs_bp, url_prefix="/runs")
v1_bp.register_blueprint(reports_bp, url_prefix="/reports")
v1_bp.register_blueprint(health_bp, url_prefix="/health")

__all__ = ["v1_bp"]
