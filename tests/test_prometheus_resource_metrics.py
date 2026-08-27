import json

from ada.infrastructure import prometheus_metrics as metrics


def test_llm_token_usage_is_split_by_component():
    initial_total = metrics.LLM_TOKENS_TOTAL.labels(component="total")._value.get()
    values = metrics.set_llm_token_usage(
        {"system": 100, "memory": 40, "tools": 20, "tool_response": 30, "prompt": 10}, response="respuesta de prueba"
    )

    assert values["system"] == 100
    assert values["memory"] == 40
    assert values["tools"] == 20
    assert values["tool_response"] == 30
    assert values["prompt"] == 10
    assert values["response"] == metrics.estimate_token_count("respuesta de prueba")
    assert values["total"] == sum(values[name] for name in ("system", "memory", "tools", "tool_response", "prompt", "response"))
    assert metrics.LLM_TOKEN_USAGE.labels(component="total")._value.get() == values["total"]
    assert metrics.LLM_TOKENS_TOTAL.labels(component="total")._value.get() == initial_total + values["total"]


def test_grafana_dashboard_schema():
    from pathlib import Path
    dashboard_file = Path(__file__).resolve().parents[1] / "monitoring" / "grafana" / "dashboards" / "ada-overview.json"
    assert dashboard_file.is_file()
    data = json.loads(dashboard_file.read_text(encoding="utf-8"))
    assert data["uid"] == "ada-overview"
    rows = [p["title"] for p in data["panels"] if p.get("type") == "row"]
    assert "TOKENS Y CONTEXTO LLM" in rows
    assert "ESTADO GENERAL" in rows
    assert "OLLAMA Y MODELOS LOCALES" in rows



def test_ollama_model_blob_digest_reads_model_layer(tmp_path):
    manifest = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "demo" / "latest"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "layers": [
                    {"mediaType": "application/vnd.ollama.image.template", "digest": "sha256:template"},
                    {"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:model-blob"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert metrics._ollama_model_blob_digest("demo:latest", str(tmp_path)) == "model-blob"


def test_ollama_resources_are_attributed_to_loaded_model(monkeypatch):
    model = "test-resource-model:latest"
    monkeypatch.setattr(
        metrics,
        "_running_ollama_models",
        lambda: [{"name": model, "size_vram": 256}],
    )
    monkeypatch.setattr(metrics, "_ollama_model_blob_digest", lambda _model: "abc123")

    metrics._refresh_ollama_model_resources(
        [
            {"command": "ollama serve", "memory": 10, "cpu": 0.01, "is_runner": False},
            {"command": "llama-server --model sha256-abc123", "memory": 2048, "cpu": 0.25, "is_runner": True},
        ]
    )

    assert metrics.OLLAMA_MODEL_MEMORY.labels(model=model)._value.get() == 2048
    assert metrics.OLLAMA_MODEL_CPU.labels(model=model)._value.get() == 0.25
    assert metrics.OLLAMA_MODEL_VRAM.labels(model=model)._value.get() == 256
    assert metrics.OLLAMA_MODEL_LOADED.labels(model=model)._value.get() == 1


def test_model_manager_call_preserves_token_metrics(monkeypatch):
    from ada.infrastructure.engines.model_manager import ModelManager
    from ada.application.services.prompts import PromptWithUsage

    manager = ModelManager({"engine_provider": "ollama"})
    monkeypatch.setattr(manager, "_call_ollama", lambda prompt, **kw: "respuesta de prueba generada")

    prompt = PromptWithUsage("Hola mundo", token_usage={"system": 50, "prompt": 12, "memory": 20, "tools": 5})
    result = manager.call("ollama", prompt, ollama_model="test-model")

    assert result == "respuesta de prueba generada"
    assert metrics.LLM_TOKEN_USAGE.labels(component="system")._value.get() == 50
    assert metrics.LLM_TOKEN_USAGE.labels(component="prompt")._value.get() == 12
    assert metrics.LLM_TOKEN_USAGE.labels(component="memory")._value.get() == 20
    assert metrics.LLM_TOKEN_USAGE.labels(component="tools")._value.get() == 5
    assert metrics.LLM_TOKEN_USAGE.labels(component="response")._value.get() > 0
    assert metrics.LLM_TOKEN_USAGE.labels(component="total")._value.get() > 80
    assert metrics.LLM_TOKEN_USAGE.labels(component="libre")._value.get() > 0
