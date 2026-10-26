import json
import uuid
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from pydantic import ValidationError

from ...db.session import SessionScoped
from ...db.models import RunModel, TestResultModel, AgentModel
from ...schemas.run_result import (
    RunCreateRequest,
    RunResponse,
    TestResultResponse,
)
from ...security import get_security_test
from ...benchmarks import get_benchmark_test
from ...core.runner import TestRunner, request_run_cancellation
from ...core.events import event_bus, format_sse

runs_bp = Blueprint("runs", __name__)


def _ensure_demo_agents(session):
    """Seed demo agents if not already in database."""
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
    session.commit()


@runs_bp.route("", methods=["POST"])
def create_run():
    """Create and trigger an evaluation run asynchronously."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        run_in = RunCreateRequest.model_validate(data)
    except ValidationError as e:
        safe_errors = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in e.errors()
        ]
        return jsonify({"error": "Validation error", "details": safe_errors}), 422
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session = SessionScoped()
    _ensure_demo_agents(session)

    # 1. Verify agent existence
    agent = session.query(AgentModel).filter_by(id=run_in.agent_id).first()
    if not agent:
        return jsonify({"error": f"Agent '{run_in.agent_id}' does not exist."}), 404

    # 2. Verify selected test IDs
    all_invalid = []
    for tid in run_in.test_selection.security:
        if not get_security_test(tid):
            all_invalid.append(tid)
    for tid in run_in.test_selection.benchmarks:
        if not get_benchmark_test(tid):
            all_invalid.append(tid)

    if all_invalid:
        return jsonify({
            "error": "Invalid test selection",
            "unknown_test_ids": all_invalid,
        }), 400

    # 3. Apply backend-enforced limits
    user_limits = run_in.limits.model_dump() if run_in.limits else {}
    max_tests_limit = current_app.config.get("MAX_TESTS_LIMIT", 20)
    max_dur_limit = current_app.config.get("MAX_DURATION_SECONDS_LIMIT", 180)
    max_ret_limit = current_app.config.get("MAX_RETRIES_LIMIT", 3)

    enforced_limits = {
        "max_tests": min(int(user_limits.get("max_tests", 10)), max_tests_limit),
        "max_duration_seconds": min(int(user_limits.get("max_duration_seconds", 60)), max_dur_limit),
        "max_retries": min(int(user_limits.get("max_retries", 1)), max_ret_limit),
    }

    # 4. Create Run Record
    run_id = str(uuid.uuid4())
    new_run = RunModel(
        id=run_id,
        agent_id=agent.id,
        test_selection=run_in.test_selection.model_dump(),
        limits=enforced_limits,
        status="queued",
    )
    session.add(new_run)
    session.commit()

    # 5. Launch background execution
    runner = TestRunner(run_id=run_id, app=current_app._get_current_object())
    runner.start_async()

    return jsonify({"run_id": run_id, "status": "queued"}), 201


@runs_bp.route("", methods=["GET"])
def list_runs():
    """List runs with pagination and optional status filter."""
    session = SessionScoped()
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(max(int(request.args.get("limit", 10)), 1), 50)
    status_filter = request.args.get("status", "").strip().lower()

    query = session.query(RunModel)
    if status_filter:
        query = query.filter(RunModel.status == status_filter)

    total = query.count()
    runs = query.order_by(RunModel.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    items = []
    for r in runs:
        results = session.query(TestResultModel).filter_by(run_id=r.id).all()
        counts = {
            "total": len(results),
            "passed": sum(1 for res in results if res.status == "passed"),
            "failed": sum(1 for res in results if res.status == "failed"),
            "inconclusive": sum(1 for res in results if res.status == "inconclusive"),
            "error": sum(1 for res in results if res.status == "error"),
        }
        items.append(
            RunResponse(
                id=r.id,
                agent_id=r.agent_id,
                agent_name=r.agent.name if r.agent else "Unknown",
                status=r.status,
                created_at=r.created_at.isoformat(),
                started_at=r.started_at.isoformat() if r.started_at else None,
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                total_duration_ms=r.total_duration_ms,
                overall_grade=r.overall_grade,
                component_scores=r.component_scores,
                test_counts=counts,
                error_message=r.error_message,
            ).model_dump()
        )

    return jsonify({
        "runs": items,
        "total": total,
        "page": page,
        "limit": limit,
    }), 200


@runs_bp.route("/<run_id>", methods=["GET"])
def get_run(run_id: str):
    """Retrieve run status, summary, and component scores."""
    session = SessionScoped()
    r = session.query(RunModel).filter_by(id=run_id).first()
    if not r:
        return jsonify({"error": f"Run '{run_id}' not found."}), 404

    results = session.query(TestResultModel).filter_by(run_id=r.id).all()
    counts = {
        "total": len(results),
        "passed": sum(1 for res in results if res.status == "passed"),
        "failed": sum(1 for res in results if res.status == "failed"),
        "inconclusive": sum(1 for res in results if res.status == "inconclusive"),
        "error": sum(1 for res in results if res.status == "error"),
    }

    resp = RunResponse(
        id=r.id,
        agent_id=r.agent_id,
        agent_name=r.agent.name if r.agent else "Unknown",
        status=r.status,
        created_at=r.created_at.isoformat(),
        started_at=r.started_at.isoformat() if r.started_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
        total_duration_ms=r.total_duration_ms,
        overall_grade=r.overall_grade,
        component_scores=r.component_scores,
        test_counts=counts,
        error_message=r.error_message,
    )
    return jsonify(resp.model_dump()), 200


@runs_bp.route("/<run_id>/results", methods=["GET"])
def get_run_results(run_id: str):
    """Retrieve individual test results and evidence for a run."""
    session = SessionScoped()
    r = session.query(RunModel).filter_by(id=run_id).first()
    if not r:
        return jsonify({"error": f"Run '{run_id}' not found."}), 404

    results = session.query(TestResultModel).filter_by(run_id=run_id).order_by(TestResultModel.created_at).all()
    resp_results = [
        TestResultResponse(
            id=res.id,
            run_id=res.run_id,
            test_id=res.test_id,
            test_title=res.test_title,
            category=res.category,
            status=res.status,
            summary=res.summary,
            latency_ms=res.latency_ms,
            tool_call_count=res.tool_call_count,
            retry_count=res.retry_count,
            token_usage=res.token_usage,
            evidence=res.evidence or {},
            created_at=res.created_at.isoformat(),
        ).model_dump()
        for res in results
    ]

    return jsonify({"results": resp_results, "total": len(resp_results)}), 200


@runs_bp.route("/<run_id>/cancel", methods=["POST"])
def cancel_run(run_id: str):
    """Request cancellation of an active test run."""
    session = SessionScoped()
    r = session.query(RunModel).filter_by(id=run_id).first()
    if not r:
        return jsonify({"error": f"Run '{run_id}' not found."}), 404

    if r.status in ("completed", "failed", "cancelled"):
        return jsonify({"message": f"Run is already in terminal state '{r.status}'."}), 400

    cancelled = request_run_cancellation(run_id)
    r.status = "cancelled"
    r.error_message = "Cancellation requested by user."
    session.commit()

    return jsonify({
        "message": f"Run '{run_id}' cancellation requested.",
        "active_worker_signaled": cancelled,
        "status": "cancelled",
    }), 200


@runs_bp.route("/<run_id>/stream", methods=["GET"])
def stream_run(run_id: str):
    """
    Server-Sent Events stream of live progress and log events for a run.

    Clients should use EventSource against this endpoint. Terminal events
    (run_completed / run_failed / run_cancelled) end the stream.
    """
    session = SessionScoped()
    r = session.query(RunModel).filter_by(id=run_id).first()
    if not r:
        return jsonify({"error": f"Run '{run_id}' not found."}), 404

    def generate():
        # Initial snapshot so the console has context immediately
        snapshot = {
            "type": "snapshot",
            "run_id": run_id,
            "ts": r.created_at.isoformat() if r.created_at else None,
            "payload": {
                "status": r.status,
                "progress": (r.orchestration_metadata or {}).get("progress"),
                "error_message": r.error_message,
            },
        }
        yield format_sse(snapshot)

        # If already finished, close after snapshot
        if r.status in ("completed", "failed", "cancelled"):
            yield format_sse({
                "type": f"run_{r.status}",
                "run_id": run_id,
                "ts": r.completed_at.isoformat() if r.completed_at else None,
                "payload": {
                    "status": r.status,
                    "overall_grade": r.overall_grade,
                    "error_message": r.error_message,
                },
            })
            return

        for event in event_bus.subscribe(run_id):
            yield format_sse(event)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate()), headers=headers)
