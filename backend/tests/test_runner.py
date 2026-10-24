import uuid
from app.db.session import SessionScoped
from app.db.models import AgentModel, RunModel, TestResultModel
from app.core.runner import TestRunner, request_run_cancellation


def test_runner_vulnerable_vs_hardened(app):
    """Run full evaluation on vulnerable and hardened agents and compare grades."""
    session = SessionScoped()

    # 1. Run on vulnerable-demo
    run_vuln_id = str(uuid.uuid4())
    run_vuln = RunModel(
        id=run_vuln_id,
        agent_id="vulnerable-demo",
        test_selection={
            "security": ["sec-indirect-injection-01", "sec-canary-leak-01"],
            "benchmarks": ["bench-multi-step-tool-use-01"],
        },
        limits={"max_tests": 5, "max_duration_seconds": 30, "max_retries": 1},
        status="queued",
    )
    session.add(run_vuln)
    session.commit()

    runner_vuln = TestRunner(run_id=run_vuln_id, app=app)
    runner_vuln.run()

    # Re-fetch run and results
    session.expire_all()
    run_vuln = session.query(RunModel).filter_by(id=run_vuln_id).first()
    assert run_vuln.status == "completed"
    assert run_vuln.overall_grade is not None
    vuln_grade = float(run_vuln.overall_grade)
    assert run_vuln.total_duration_ms > 0

    results_vuln = session.query(TestResultModel).filter_by(run_id=run_vuln_id).all()
    assert len(results_vuln) == 3
    # Vulnerable agent should fail security tests
    failed_sec = [r for r in results_vuln if r.category == "security" and r.status == "failed"]
    assert len(failed_sec) >= 1

    # 2. Run on hardened-demo
    run_hard_id = str(uuid.uuid4())
    run_hard = RunModel(
        id=run_hard_id,
        agent_id="hardened-demo",
        test_selection={
            "security": ["sec-indirect-injection-01", "sec-canary-leak-01"],
            "benchmarks": ["bench-multi-step-tool-use-01"],
        },
        limits={"max_tests": 5, "max_duration_seconds": 30, "max_retries": 1},
        status="queued",
    )
    session.add(run_hard)
    session.commit()

    runner_hard = TestRunner(run_id=run_hard_id, app=app)
    runner_hard.run()

    session.expire_all()
    run_hard = session.query(RunModel).filter_by(id=run_hard_id).first()
    assert run_hard.status == "completed"
    hard_grade = float(run_hard.overall_grade)

    # Hardened agent must achieve a significantly higher grade than vulnerable agent!
    assert hard_grade > vuln_grade


def test_runner_limit_enforcement(app):
    """Verify that test runner enforces max_tests limit."""
    session = SessionScoped()
    run_id = str(uuid.uuid4())
    run = RunModel(
        id=run_id,
        agent_id="hardened-demo",
        test_selection={
            "security": ["sec-indirect-injection-01", "sec-canary-leak-01", "sec-unauthorized-tool-01"],
            "benchmarks": ["bench-multi-step-tool-use-01"],
        },
        limits={"max_tests": 2, "max_duration_seconds": 30, "max_retries": 1},
        status="queued",
    )
    session.add(run)
    session.commit()

    runner = TestRunner(run_id=run_id, app=app)
    runner.run()

    session.expire_all()
    results = session.query(TestResultModel).filter_by(run_id=run_id).all()
    # Must not exceed max_tests of 2
    assert len(results) == 2


def test_run_cancellation(app):
    """Verify cancellation signaling."""
    run_id = str(uuid.uuid4())
    cancelled = request_run_cancellation(run_id)
    # Not active in registry yet
    assert cancelled is False


def test_runner_isolation(app):
    """Verify results from different runs do not cross-contaminate."""
    session = SessionScoped()
    r1_id = str(uuid.uuid4())
    r2_id = str(uuid.uuid4())

    r1 = RunModel(id=r1_id, agent_id="hardened-demo", test_selection={"security": ["sec-canary-leak-01"]}, limits={}, status="queued")
    r2 = RunModel(id=r2_id, agent_id="vulnerable-demo", test_selection={"security": ["sec-canary-leak-01"]}, limits={}, status="queued")
    session.add_all([r1, r2])
    session.commit()

    TestRunner(r1_id, app).run()
    TestRunner(r2_id, app).run()

    r1_results = session.query(TestResultModel).filter_by(run_id=r1_id).all()
    r2_results = session.query(TestResultModel).filter_by(run_id=r2_id).all()

    assert len(r1_results) == 1
    assert len(r2_results) == 1
    assert r1_results[0].status == "passed"
    assert r2_results[0].status == "failed"
