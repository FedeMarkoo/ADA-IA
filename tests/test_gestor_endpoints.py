"""Unit tests for the new Gestor Web API endpoints, lifecycle controls and Health Doctor."""

import json
from ada.interfaces.web.server import create_app


def test_gestor_endpoints():
    app = create_app({"allowed_roots": ["/tmp"]})
    client = app.test_client()

    # Get CSRF token
    client.get("/").close()
    csrf_token = client.get_cookie("ada_csrf").value
    headers = {"X-ADA-Token": csrf_token, "Content-Type": "application/json"}

    # 1. Healthcheck & Doctor
    res = client.get("/api/healthcheck")
    assert res.status_code == 200
    data = res.get_json()
    assert "overall_status" in data
    assert "score" in data
    assert "items" in data
    assert len(data["items"]) >= 5

    res = client.post("/api/healthcheck/heal", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    res = client.post("/api/healthcheck/fix/restart_agent", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    # 2. Ollama status
    res = client.get("/api/ollama/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "health" in data
    assert "runtime" in data

    # 3. Models catalog & policy
    res = client.get("/api/models/catalog")
    assert res.status_code == 200
    data = res.get_json()
    assert "catalog" in data
    assert "roles" in data

    res = client.get("/api/models/policy")
    assert res.status_code == 200
    data = res.get_json()
    assert "models" in data
    assert "active" in data

    # 4. MCPs servers & tools
    res = client.get("/api/mcps/servers")
    assert res.status_code == 200
    data = res.get_json()
    assert "servers" in data

    res = client.get("/api/mcps/tools")
    assert res.status_code == 200
    data = res.get_json()
    assert "tools" in data

    # 5. MCP Lifecycle Controls
    res = client.post("/api/mcps/servers/filesystem/stop", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    res = client.post("/api/mcps/servers/filesystem/start", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    res = client.post("/api/mcps/servers/filesystem/restart", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    res = client.post("/api/mcps/servers/restart-all", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    res = client.get("/api/mcps/servers/filesystem/ping")
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    # 6. ADA Agent Restart
    res = client.post("/api/agent/restart", headers=headers)
    assert res.status_code == 200
    assert res.get_json().get("ok") is True

    # 7. Memory stats
    res = client.get("/api/memory/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert "audit_count" in data
    assert "db_path" in data
