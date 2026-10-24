def test_default_demo_agents_seeded(client):
    """Verify default demo agents (vulnerable-demo and hardened-demo) are seeded on startup."""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] >= 2
    agent_ids = [a["id"] for a in data["agents"]]
    assert "vulnerable-demo" in agent_ids
    assert "hardened-demo" in agent_ids


def test_register_and_retrieve_agent(client):
    """Test registering a custom agent and fetching it."""
    payload = {
        "name": "Custom Test Agent",
        "adapter_type": "http",
        "config": {
            "endpoint_url": "https://api.example.com/agent",
            "model": "custom-v1",
        },
        "description": "Integration test agent",
    }
    create_resp = client.post("/api/v1/agents", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.get_json()
    agent_id = created["id"]
    assert created["name"] == "Custom Test Agent"
    assert created["adapter_type"] == "http"

    # Retrieve by ID
    get_resp = client.get(f"/api/v1/agents/{agent_id}")
    assert get_resp.status_code == 200
    retrieved = get_resp.get_json()
    assert retrieved["id"] == agent_id
    assert retrieved["name"] == "Custom Test Agent"


def test_reject_secret_in_agent_config(client):
    """Verify that storing secrets/api_keys directly in config is rejected."""
    payload = {
        "name": "Insecure Agent",
        "adapter_type": "openai",
        "config": {
            "api_key": "sk-secret-plain-text-key",
        },
    }
    response = client.post("/api/v1/agents", json=payload)
    assert response.status_code in (400, 422)


def test_reject_invalid_adapter_type(client):
    """Verify that unknown adapter types are rejected by validation."""
    payload = {
        "name": "Invalid Adapter Agent",
        "adapter_type": "unsupported-adapter",
        "config": {},
    }
    response = client.post("/api/v1/agents", json=payload)
    assert response.status_code in (400, 422)


def test_delete_agent(client):
    """Verify agent deletion."""
    payload = {
        "name": "Agent to Delete",
        "adapter_type": "mock",
        "config": {},
    }
    create_resp = client.post("/api/v1/agents", json=payload)
    agent_id = create_resp.get_json()["id"]

    del_resp = client.delete(f"/api/v1/agents/{agent_id}")
    assert del_resp.status_code == 200

    # Ensure 404 after deletion
    get_resp = client.get(f"/api/v1/agents/{agent_id}")
    assert get_resp.status_code == 404
