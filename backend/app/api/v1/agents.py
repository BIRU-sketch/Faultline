import uuid
from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from ...db.session import SessionScoped
from ...db.models import AgentModel
from ...schemas.agent import AgentCreate, AgentResponse, AgentListResponse

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("", methods=["GET"])
def list_agents():
    """List all registered agents."""
    session = SessionScoped()
    agents = session.query(AgentModel).order_by(AgentModel.created_at.desc()).all()

    result = [
        AgentResponse(
            id=a.id,
            name=a.name,
            adapter_type=a.adapter_type,
            config=a.config or {},
            description=a.description,
            enabled=a.enabled,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
        ).model_dump()
        for a in agents
    ]

    return jsonify({"agents": result, "total": len(result)}), 200


@agents_bp.route("", methods=["POST"])
def register_agent():
    """Register a new target agent configuration."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        agent_in = AgentCreate.model_validate(data)
    except ValidationError as e:
        safe_errors = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in e.errors()
        ]
        return jsonify({"error": "Validation error", "details": safe_errors}), 422
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session = SessionScoped()
    agent_id = str(uuid.uuid4())

    new_agent = AgentModel(
        id=agent_id,
        name=agent_in.name,
        adapter_type=agent_in.adapter_type.value,
        config=agent_in.config,
        description=agent_in.description,
        enabled=True,
    )
    session.add(new_agent)
    session.commit()

    resp = AgentResponse(
        id=new_agent.id,
        name=new_agent.name,
        adapter_type=new_agent.adapter_type,
        config=new_agent.config or {},
        description=new_agent.description,
        enabled=new_agent.enabled,
        created_at=new_agent.created_at.isoformat(),
        updated_at=new_agent.updated_at.isoformat(),
    )
    return jsonify(resp.model_dump()), 201


@agents_bp.route("/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """Retrieve one agent configuration."""
    session = SessionScoped()
    agent = session.query(AgentModel).filter_by(id=agent_id).first()
    if not agent:
        return jsonify({"error": f"Agent '{agent_id}' not found."}), 404

    resp = AgentResponse(
        id=agent.id,
        name=agent.name,
        adapter_type=agent.adapter_type,
        config=agent.config or {},
        description=agent.description,
        enabled=agent.enabled,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
    )
    return jsonify(resp.model_dump()), 200


@agents_bp.route("/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id: str):
    """Remove an agent configuration and its associated runs."""
    session = SessionScoped()
    agent = session.query(AgentModel).filter_by(id=agent_id).first()
    if not agent:
        return jsonify({"error": f"Agent '{agent_id}' not found."}), 404

    session.delete(agent)
    session.commit()
    return jsonify({"message": f"Agent '{agent_id}' deleted successfully."}), 200
