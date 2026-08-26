from ada.capabilities.data.transport_status import run
from ada.infrastructure.engines.provider_router import ProviderRouter
from ada.infrastructure.runtime.presence import PresenceStore


def test_provider_router_prefers_local_for_high_privacy():
    router = ProviderRouter(
        {
            "provider_router": {
                "providers": [
                    {"name": "gemini", "priority": 20},
                    {"name": "ollama", "local": True, "priority": 1},
                ]
            }
        }
    )
    assert router.choose({"privacy": "high"}, {"gemini": True, "ollama": True}, []) == "ollama"


def test_provider_router_skips_exhausted_token_budget():
    router = ProviderRouter(
        {
            "provider_router": {
                "sort": "price",
                "providers": [
                    {"name": "gemini", "monthly_token_limit": 100, "price_per_million_tokens": 0},
                    {"name": "openrouter", "monthly_token_limit": 10000, "price_per_million_tokens": 1},
                ],
            }
        }
    )
    router.record("gemini", 100)
    assert router.choose({"estimated_tokens": 200}, {"gemini": True, "openrouter": True}, []) == "openrouter"


def test_transport_status_fails_closed_without_token():
    result = run({"line": "sarmiento", "config": {"api_token": ""}})
    assert result["ok"] is False
    assert result["status"] == "unknown"
    assert result["error"] == "transport_api_token_missing"


def test_presence_store_respects_ttl(tmp_path):
    store = PresenceStore(str(tmp_path / "presence.json"))
    stored = store.set("work", ttl_seconds=60, source="test")
    assert stored["location"] == "work"
    assert store.get("work")["active"] is True
    assert store.get("home")["active"] is False
