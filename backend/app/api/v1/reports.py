from flask import Blueprint, jsonify
from ...db.session import SessionScoped
from ...db.models import RunModel, TestResultModel
from ...schemas.run_result import TestResultResponse
from ...schemas.grade import ReportResponse, GradeReportSchema
from ...core.grader import TenPointGrader

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/<run_id>", methods=["GET"])
def get_report(run_id: str):
    """Return a comprehensive, detailed evaluation report for a run."""
    session = SessionScoped()
    r = session.query(RunModel).filter_by(id=run_id).first()
    if not r:
        return jsonify({"error": f"Run '{run_id}' not found."}), 404

    results = session.query(TestResultModel).filter_by(run_id=run_id).order_by(TestResultModel.created_at).all()

    # Separate security results and benchmark results
    sec_results = []
    bench_results = []
    results_dicts = []

    for res in results:
        res_schema = TestResultResponse(
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
        )
        if res.category == "security":
            sec_results.append(res_schema)
        else:
            bench_results.append(res_schema)

        results_dicts.append({
            "test_id": res.test_id,
            "test_title": res.test_title,
            "category": res.category,
            "status": res.status,
            "latency_ms": res.latency_ms,
            "tool_call_count": res.tool_call_count,
            "retry_count": res.retry_count,
            "evidence": res.evidence or {},
        })

    counts = {
        "total": len(results),
        "passed": sum(1 for res in results if res.status == "passed"),
        "failed": sum(1 for res in results if res.status == "failed"),
        "inconclusive": sum(1 for res in results if res.status == "inconclusive"),
        "error": sum(1 for res in results if res.status == "error"),
    }

    grader = TenPointGrader()
    grading_report: GradeReportSchema = grader.grade(results_dicts)
    recommendations = grader.generate_recommendations(results_dicts)

    report = ReportResponse(
        run_id=r.id,
        agent_id=r.agent_id,
        agent_name=r.agent.name if r.agent else "Unknown",
        adapter_type=r.agent.adapter_type if r.agent else "unknown",
        status=r.status,
        timestamps={
            "created_at": r.created_at.isoformat(),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        },
        total_duration_ms=r.total_duration_ms,
        summary_counts=counts,
        grading=grading_report,
        security_results=sec_results,
        benchmark_results=bench_results,
        recommendations=recommendations,
        limitations=grading_report.limitations,
        progress=(r.orchestration_metadata or {}).get("progress"),
    )
    data = report.model_dump()
    data["openai_synthesis"] = r.final_report
    data["orchestration"] = r.orchestration_metadata or {}
    return jsonify(data), 200
