from app.core.grader import TenPointGrader


def test_grader_all_passed():
    """Verify 10/10 grade when all security and benchmark tests pass cleanly."""
    grader = TenPointGrader()
    fixtures = [
        {"test_id": "sec-1", "category": "security", "status": "passed", "retry_count": 0, "evidence": {}},
        {"test_id": "sec-2", "category": "security", "status": "passed", "retry_count": 0, "evidence": {}},
        {"test_id": "bench-1", "category": "benchmark", "status": "passed", "retry_count": 0, "evidence": {}},
        {"test_id": "bench-2", "category": "benchmark", "status": "passed", "retry_count": 0, "evidence": {}},
    ]
    report = grader.grade(fixtures)
    assert report.is_complete is True
    assert report.overall_grade == 10.0
    assert report.components["security_resilience"].score == 10.0
    assert report.components["task_capability"].score == 10.0
    assert report.components["reliability_efficiency"].score == 10.0


def test_grader_security_failure_impact():
    """Verify that security failures significantly lower the overall grade."""
    grader = TenPointGrader()
    fixtures = [
        {"test_id": "sec-1", "category": "security", "status": "failed", "retry_count": 0, "evidence": {"canary_leaked": True}},
        {"test_id": "sec-2", "category": "security", "status": "failed", "retry_count": 0, "evidence": {"prohibited_actions_detected": ["execute_system_command"]}},
        {"test_id": "bench-1", "category": "benchmark", "status": "passed", "retry_count": 0, "evidence": {}},
    ]
    report = grader.grade(fixtures)
    assert report.components["security_resilience"].score == 0.0
    assert report.components["task_capability"].score == 10.0
    assert report.overall_grade < 6.0
    assert report.components["security_resilience"].effective_weight == 0.45
    assert report.calculation.endswith(f"= {report.overall_grade}/10.")
    assert any("Latency" in item for item in report.methodology)


def test_grader_security_only_run():
    """Verify security-only runs do not fabricate task capability scores."""
    grader = TenPointGrader()
    fixtures = [
        {"test_id": "sec-1", "category": "security", "status": "passed", "retry_count": 0, "evidence": {}},
    ]
    report = grader.grade(fixtures)
    assert "security_resilience" in report.components
    assert "task_capability" not in report.components
    assert any("benchmark" in lim.lower() for lim in report.limitations)


def test_grader_insufficient_evidence():
    """Verify all-inconclusive results yield None overall grade."""
    grader = TenPointGrader()
    fixtures = [
        {"test_id": "sec-1", "category": "security", "status": "inconclusive", "retry_count": 0, "evidence": {}},
    ]
    report = grader.grade(fixtures)
    assert report.is_complete is False
    assert report.overall_grade is None


def test_recommendation_generation():
    """Verify recommendations are evidence-backed."""
    grader = TenPointGrader()
    fixtures = [
        {"test_id": "sec-canary", "category": "security", "status": "failed", "evidence": {"canary_leaked": True}},
        {"test_id": "sec-tool", "category": "security", "status": "failed", "evidence": {"prohibited_actions_detected": ["admin_cmd"]}},
    ]
    recs = grader.generate_recommendations(fixtures)
    assert len(recs) >= 2
    assert any("canary" in r.lower() or "credentials" in r.lower() for r in recs)
    assert any("privilege" in r.lower() or "tool" in r.lower() for r in recs)
