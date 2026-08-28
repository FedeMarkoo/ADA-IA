import unittest
from prometheus_client import generate_latest

from ada.infrastructure.prometheus_metrics import (
    REGISTRY,
    HEALTHCHECK_RUNS,
    HEALTHCHECK_DURATION,
    HEALTHCHECK_JUDGE_SCORE,
    HEALTHCHECK_BATCH_RUNS,
    HEALTHCHECK_ACTIVE_BATCHES,
    HEALTHCHECK_PASS_RATE,
    ROUTER_DECISIONS,
    ROUTER_CONFIDENCE,
    ROUTER_ERRORS,
    ROUTER_FALLBACKS,
    LLM_GENERATION_SPEED,
    LLM_CONTEXT_SATURATION,
    LLM_RETRIES,
    SQLITE_QUERIES,
    SQLITE_QUERY_DURATION,
    MEMORY_REFINER_RUNS,
    MEMORY_REFINER_FACTS,
    TELEGRAM_MESSAGES,
    TELEGRAM_LATENCY,
    TELEGRAM_POLLING_ERRORS,
    SYSTEM_ERRORS,
    exposition,
    record_healthcheck_run,
    record_healthcheck_judge,
    record_healthcheck_batch,
    set_active_healthcheck_batches,
    update_category_pass_rate,
    record_router_decision,
    record_router_error,
    record_router_fallback,
    record_llm_generation,
    record_llm_retry,
    record_sqlite_op,
    record_memory_refiner,
    record_telegram_event,
    record_telegram_error,
    record_system_error,
)
from ada.application.router import IntentRouter
from ada.application.services.web_chat import WebChatService
from ada.infrastructure.persistence.sqlite import Memory
from ada.mcps.manager import MCPManager


class ExtendedPrometheusMetricsTests(unittest.TestCase):
    def test_healthcheck_metrics_recording(self):
        record_healthcheck_run("calendar", "next_calendar_event", "passed", 0.45)
        record_healthcheck_judge("calendar", "llama3.2:3b", 0.95)
        record_healthcheck_batch("started")
        record_healthcheck_batch("completed")
        set_active_healthcheck_batches(3)
        update_category_pass_rate("calendar", 0.88)

        self.assertGreaterEqual(
            HEALTHCHECK_RUNS.labels(category="calendar", capability="next_calendar_event", status="passed")._value.get(),
            1,
        )
        self.assertEqual(HEALTHCHECK_ACTIVE_BATCHES._value.get(), 3)
        self.assertAlmostEqual(HEALTHCHECK_PASS_RATE.labels(category="calendar")._value.get(), 0.88)

    def test_router_metrics_recording(self):
        record_router_decision("mcp_call", intent_type="tools", status="ok", confidence=0.92)
        record_router_error("mcp_router_failed")
        record_router_fallback("deterministic_calendar")

        self.assertGreaterEqual(
            ROUTER_DECISIONS.labels(action="mcp_call", intent_type="tools", status="ok")._value.get(), 1
        )
        self.assertGreaterEqual(ROUTER_ERRORS.labels(error_type="mcp_router_failed")._value.get(), 1)
        self.assertGreaterEqual(ROUTER_FALLBACKS.labels(trigger="deterministic_calendar")._value.get(), 1)

    def test_llm_metrics_recording(self):
        record_llm_generation("llama3.2:3b", 120, 2.0, context_used=1024, context_max=4096)
        record_llm_retry("llama3.2:3b", "timeout")

        self.assertAlmostEqual(LLM_CONTEXT_SATURATION.labels(model="llama3.2:3b")._value.get(), 0.25)
        self.assertGreaterEqual(LLM_RETRIES.labels(model="llama3.2:3b", reason="timeout")._value.get(), 1)

    def test_sqlite_and_memory_refiner_metrics(self):
        record_sqlite_op("memories", "select", duration=0.002)
        record_memory_refiner("ok", extracted_facts=3)

        self.assertGreaterEqual(SQLITE_QUERIES.labels(table="memories", operation="select")._value.get(), 1)
        self.assertGreaterEqual(MEMORY_REFINER_RUNS.labels(status="ok")._value.get(), 1)
        self.assertGreaterEqual(MEMORY_REFINER_FACTS._value.get(), 3)

    def test_telegram_and_system_metrics(self):
        record_telegram_event("inbound", "ok", duration=0.35)
        record_telegram_error("network_timeout")
        record_system_error("router", "ValueError")

        self.assertGreaterEqual(TELEGRAM_MESSAGES.labels(direction="inbound", status="ok")._value.get(), 1)
        self.assertGreaterEqual(TELEGRAM_POLLING_ERRORS.labels(error_type="network_timeout")._value.get(), 1)
        self.assertGreaterEqual(SYSTEM_ERRORS.labels(component="router", error_class="valueerror")._value.get(), 1)

    def test_exposition_contains_new_metrics(self):
        payload = exposition().decode("utf-8")
        self.assertIn("ada_healthcheck_runs_total", payload)
        self.assertIn("ada_healthcheck_active_batches", payload)
        self.assertIn("ada_router_decisions_total", payload)
        self.assertIn("ada_llm_generation_speed_tokens_per_second", payload)
        self.assertIn("ada_sqlite_queries_total", payload)
        self.assertIn("ada_memory_refiner_runs_total", payload)
        self.assertIn("ada_telegram_messages_total", payload)

    def test_router_deterministic_mcp_fallback(self):
        memory = Memory(":memory:")
        mcp_manager = MCPManager(config={})
        router = IntentRouter(model_manager=None, config={}, memory=memory, mcp_manager=mcp_manager)

        calendar_res = router._deterministic_mcp_fallback("¿Cuál es mi próximo evento de calendar?")
        self.assertEqual(calendar_res.get("action"), "mcp_call")
        self.assertEqual(calendar_res.get("tool"), "google_calendar.list_events")

        gmail_res = router._deterministic_mcp_fallback("Leé mi último correo de gmail")
        self.assertEqual(gmail_res.get("action"), "mcp_call")
        self.assertEqual(gmail_res.get("tool"), "gmail.read_inbox")

        web_res = router._deterministic_mcp_fallback("Buscá en internet noticias sobre inteligencia artificial")
        self.assertEqual(web_res.get("action"), "mcp_call")
        self.assertEqual(web_res.get("tool"), "web_search.search")

    def test_filesystem_intent_ignores_gmail_and_conversational_requests(self):
        # Gmail query with word "fotos" should not be treated as local filesystem
        self.assertIsNone(WebChatService._filesystem_intent("Buscá en Gmail conversaciones relacionadas con fotos Sofia"))
        self.assertIsNone(WebChatService._filesystem_intent("Buscá en mi correo el mail de las fotos"))
        self.assertIsNone(WebChatService._filesystem_intent("Revisá mi calendario para ver qué eventos tengo"))
        self.assertIsNone(WebChatService._filesystem_intent("Ayudame con las fotos del viaje"))


if __name__ == "__main__":
    unittest.main()
