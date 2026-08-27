import json

from ada.infrastructure import prometheus_metrics as metrics


def test_llm_token_usage_is_split_by_component():
    values = metrics.set_llm_token_usage(
        {"system": 100, "memory": 40, "tools": 20, "prompt": 10}, response="respuesta de prueba"
    )

    assert values["system"] == 100
    assert values["memory"] == 40
    assert values["tools"] == 20
    assert values["prompt"] == 10
    assert values["response"] == metrics.estimate_token_count("respuesta de prueba")
    assert values["total"] == sum(values[name] for name in ("system", "memory", "tools", "prompt", "response"))
    assert metrics.LLM_TOKEN_USAGE.labels(component="total")._value.get() == values["total"]


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
