from flask import Blueprint, jsonify
from sqlalchemy import text
from ...db.session import SessionScoped

health_bp = Blueprint("health", __name__)


@health_bp.route("", methods=["GET"])
def health_check():
    """Health check endpoint to report service and database availability."""
    session = SessionScoped()
    db_status = "unavailable"
    try:
        session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    is_ok = db_status == "healthy"
    status_code = 200 if is_ok else 503

    return jsonify({
        "status": "healthy" if is_ok else "degraded",
        "service": "faultline-backend",
        "database": db_status,
        "version": "1.0.0",
    }), status_code
