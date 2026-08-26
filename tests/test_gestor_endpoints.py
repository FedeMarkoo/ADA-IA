import json
import tempfile
import unittest

try:
    from ada.interfaces.web.server import create_app
except ImportError:
    create_app = None


def test_gestor_endpoints():
    if create_app is None:
        raise unittest.SkipTest("Flask is not installed (optional web extra)")
    trigger_state = tempfile.TemporaryDirectory()
    app = create_app(
        {
            "allowed_roots": ["/tmp"],
            "db_path": ":memory:",
            "trigger_state_dir": trigger_state.name,
            "discover_external_triggers": False,
            "telegram": {"enabled": False, "token": ""},
        }
    )
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

    # Live ADA core exposes its topology and real execution phases.
    res = client.get("/api/core/state")
    assert res.status_code == 200
    core = res.get_json()
    assert "activity" in core
    assert "active" in core["models"]
    assert "telegram" in core["connectors"]
    assert isinstance(core["connectors"]["mcps"], list)
    assert isinstance(core["connectors"]["triggers"], list)
    assert core["telemetry"] == {"source": "prometheus", "dashboard": "grafana"}

    res = client.get("/api/triggers")
    assert res.status_code == 200
    triggers = res.get_json()
    assert [item["id"] for item in triggers["triggers"]] == [
        "telegram",
        "removable-device",
        "calendar",
        "cron",
        "webhook",
    ]
    assert triggers["triggers"][0]["managed_externally"] is True
    assert triggers["triggers"][1]["status"] == "ready"

    res = client.post("/api/chat", headers=headers, data=json.dumps({"message": "hola", "lang": "es"}))
    assert res.status_code == 200
    core = client.get("/api/core/state").get_json()
    assert core["activity"]["status"] == "complete"
    assert [event["phase"] for event in core["activity"]["recent"]][-2:] == ["received", "completed"]

    # Agent patience is configurable and remains independent from model mode.
    res = client.get("/api/ollama/config")
    assert res.status_code == 200
    timeout_data = res.get_json()
    assert timeout_data["timeout_profile"] == "patient"
    assert timeout_data["chat_timeout_seconds"] == 900
    assert "patient" in timeout_data["timeout_presets"]

    res = client.post(
        "/api/ollama/config",
        headers=headers,
        data=json.dumps(
            {
                "timeout_profile": "custom",
                "router_timeout": 42,
                "model_timeout": 240,
                "chat_timeout_seconds": 1200,
                "food_advisor_timeout": 180,
            }
        ),
    )
    assert res.status_code == 200
    assert res.get_json()["config"]["chat_timeout_seconds"] == 1200

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

    res = client.post("/api/models/policy", headers=headers, data=json.dumps({"selection_mode": "hybrid"}))
    assert res.status_code == 200
    res = client.get("/api/ollama/config")
    assert res.get_json()["chat_timeout_seconds"] == 1200
    assert res.get_json()["timeout_profile"] == "custom"

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

    # 7. Ollama Load & Preload endpoints
    res = client.post("/api/ollama/load", headers=headers, data=json.dumps({"model": "test-model"}))
    assert res.status_code == 200
    assert "ok" in res.get_json()

    res = client.post("/api/ollama/preload_all", headers=headers)
    assert res.status_code == 200
    assert "running" in res.get_json()

    # 8. Memory stats
    res = client.get("/api/memory/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert "audit_count" in data
    assert "db_path" in data
