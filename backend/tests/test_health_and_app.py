def test_health_endpoint(client):
    """Test health check endpoint reports service and database health."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "faultline-backend"
    assert data["database"] == "healthy"


def test_404_handling(client):
    """Test consistent JSON error responses for unknown routes."""
    response = client.get("/api/v1/unknown-endpoint")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_dashboard_and_assets_are_served_by_flask(client):
    page = client.get("/")
    script = client.get("/assets/app.js")

    assert page.status_code == 200
    assert b"Faultline" in page.data
    assert script.status_code == 200
    assert b"run_id" in script.data
