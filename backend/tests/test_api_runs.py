import time


def test_api_run_workflow(client):
    """Test end-to-end API run creation, polling, results, and report retrieval."""
    payload = {
        "agent_id": "hardened-demo",
        "test_selection": {
            "security": ["sec-indirect-injection-01", "sec-canary-leak-01"],
            "benchmarks": ["bench-multi-step-tool-use-01"],
        },
        "limits": {
            "max_tests": 8,
            "max_retries": 2,
            "max_duration_seconds": 60,
        },
    }

    # 1. Create run
    create_resp = client.post("/api/v1/runs", json=payload)
    assert create_resp.status_code == 201
    data = create_resp.get_json()
    assert "run_id" in data
    assert data["status"] == "queued"
    run_id = data["run_id"]

    # 2. Wait briefly for background execution to complete
    for _ in range(30):
        status_resp = client.get(f"/api/v1/runs/{run_id}")
        assert status_resp.status_code == 200
        run_data = status_resp.get_json()
        if run_data["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)

    assert run_data["status"] == "completed"
    assert run_data["overall_grade"] is not None
    assert run_data["test_counts"]["total"] == 3

    # 3. Retrieve individual test results
    results_resp = client.get(f"/api/v1/runs/{run_id}/results")
    assert results_resp.status_code == 200
    results_data = results_resp.get_json()
    assert results_data["total"] == 3
    assert len(results_data["results"]) == 3

    # 4. Retrieve complete evaluation report
    report_resp = client.get(f"/api/v1/reports/{run_id}")
    assert report_resp.status_code == 200
    report_data = report_resp.get_json()
    assert report_data["run_id"] == run_id
    assert report_data["grading"]["overall_grade"] is not None
    assert len(report_data["security_results"]) == 2
    assert len(report_data["benchmark_results"]) == 1
    assert "recommendations" in report_data


def test_api_run_reject_unknown_agent(client):
    """Reject run creation with 404 if agent does not exist."""
    payload = {
        "agent_id": "nonexistent-agent-id-12345",
        "test_selection": {
            "security": ["sec-canary-leak-01"],
        },
    }
    response = client.post("/api/v1/runs", json=payload)
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_api_run_reject_unknown_tests(client):
    """Reject run creation with 400 if test IDs are not recognized."""
    payload = {
        "agent_id": "vulnerable-demo",
        "test_selection": {
            "security": ["nonexistent-test-id-9999"],
        },
    }
    response = client.post("/api/v1/runs", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert "unknown_test_ids" in data


def test_api_run_cancellation_endpoint(client):
    """Test cancelling an existing run."""
    payload = {
        "agent_id": "hardened-demo",
        "test_selection": {
            "security": ["sec-canary-leak-01"],
        },
    }
    create_resp = client.post("/api/v1/runs", json=payload)
    run_id = create_resp.get_json()["run_id"]

    cancel_resp = client.post(f"/api/v1/runs/{run_id}/cancel")
    assert cancel_resp.status_code in (200, 400)
