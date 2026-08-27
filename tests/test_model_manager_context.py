import json
from unittest.mock import MagicMock, patch
import pytest
from ada.infrastructure.engines.model_manager import ModelManager
from ada.application.services.prompts import PromptWithUsage


def test_model_context_limit_resolution():
    config = {
        "ollama_num_ctx": 4096,
        "model_num_ctx": {
            "llama3.2:1b": 2048,
            "qwen2.5-coder:7b": 16384,
            "deepseek-r1:8b": 8192,
        },
        "model_catalog": [
            {"name": "qwen2.5vl:3b", "num_ctx": 4096},
            {"name": "custom:model", "num_ctx": 32768},
        ],
    }
    manager = ModelManager(config)

    # 1. From model_num_ctx mapping (exact name)
    assert manager.model_context_limit("llama3.2:1b") == 2048
    assert manager.model_context_limit("qwen2.5-coder:7b") == 16384
    assert manager.model_context_limit("deepseek-r1:8b") == 8192

    # 2. From model_catalog
    assert manager.model_context_limit("qwen2.5vl:3b") == 4096
    assert manager.model_context_limit("custom:model") == 32768

    # 3. Fallback to global ollama_num_ctx
    assert manager.model_context_limit("unknown:model") == 4096


def test_adaptive_context_small_prompt_optimizes_memory():
    config = {
        "ollama_num_ctx": 16384,
        "adaptive_context": True,
        "min_num_ctx": 1024,
    }
    manager = ModelManager(config)

    # Small prompt with 10 words (~15 tokens) + max_tokens 200 -> needed ~ 15 + 200 + margin -> fits in 1024
    short_prompt = "Hola Ada, ¿cómo estás hoy?"
    effective_ctx = manager.resolve_effective_num_ctx(
        "llama3.2:3b",
        prompt=short_prompt,
        max_tokens=200,
    )
    assert effective_ctx == 1024
    # Ensure it is well below the ceiling of 16384
    assert effective_ctx < manager.model_context_limit("llama3.2:3b")


def test_adaptive_context_ceiling_is_strictly_respected():
    config = {
        "ollama_num_ctx": 4096,
        "adaptive_context": True,
    }
    manager = ModelManager(config)

    # Very large prompt that would require 10000+ tokens
    huge_prompt = "palabra " * 15000
    effective_ctx = manager.resolve_effective_num_ctx(
        "llama3.2:3b",
        prompt=huge_prompt,
        max_tokens=2048,
    )
    # Must never exceed the configured ceiling of 4096
    assert effective_ctx == 4096


def test_adaptive_context_disabled_returns_configured_ceiling():
    config = {
        "ollama_num_ctx": 8192,
        "adaptive_context": False,
    }
    manager = ModelManager(config)

    short_prompt = "Hola"
    effective_ctx = manager.resolve_effective_num_ctx(
        "llama3.2:3b",
        prompt=short_prompt,
        max_tokens=100,
    )
    assert effective_ctx == 8192


def test_adaptive_context_with_prompt_token_usage():
    config = {
        "ollama_num_ctx": 16384,
        "adaptive_context": True,
        "min_num_ctx": 1024,
    }
    manager = ModelManager(config)

    # Prompt with rich token breakdown: system (500) + memory (600) + tools (400) + prompt (100) = 1600 tokens
    # + expected output (768) + 15% margin (~355) = ~2723 tokens -> steps to 3072 bucket
    usage = {"system": 500, "memory": 600, "tools": 400, "prompt": 100}
    prompt = PromptWithUsage("Prompt text", token_usage=usage)

    effective_ctx = manager.resolve_effective_num_ctx(
        "llama3.2:3b",
        prompt=prompt,
        max_tokens=768,
    )
    assert effective_ctx == 3072
    assert effective_ctx <= manager.model_context_limit("llama3.2:3b")


def test_call_ollama_sends_adaptive_num_ctx():
    config = {
        "ollama_num_ctx": 16384,
        "adaptive_context": True,
        "min_num_ctx": 1024,
    }
    manager = ModelManager(config)

    captured_payload = {}

    def fake_urlopen(req, timeout=180):
        nonlocal captured_payload
        captured_payload = json.loads(req.data.decode("utf-8"))
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"message": {"content": "Respuesta simulada"}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resp = manager._call_ollama("Hola Ada", ollama_model="llama3.2:3b", max_tokens=100)
        assert resp == "Respuesta simulada"
        assert "options" in captured_payload
        # Should be scaled adaptively to 1024 instead of 16384
        assert captured_payload["options"]["num_ctx"] == 1024
