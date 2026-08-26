import json
import concurrent.futures
from unittest.mock import MagicMock, patch

from ada.application.services.healthcheck import (
    HEALTHCHECK_PROMPTS,
    HealthcheckStore,
    evaluate,
    llm_judge,
    requires_mcp,
)
from ada.infrastructure.persistence.sqlite import Memory


def test_healthcheck_prompts_are_persisted_in_sqlite():
    memory = Memory(":memory:")
    store = HealthcheckStore(memory)
    prompts = store.prompts()
    assert len(prompts) >= 15
    assert {item["id"] for item in prompts} == {item["id"] for item in HEALTHCHECK_PROMPTS}
    assert memory.conn.execute("SELECT COUNT(*) FROM healthcheck_prompts").fetchone()[0] == len(prompts)
    assert len({item["category"] for item in prompts}) >= 6
    assert sum(item["category"] == "gmail" for item in prompts) == 3


def test_cases_can_be_added_to_an_existing_category():
    memory = Memory(":memory:")
    store = HealthcheckStore(memory)
    store.add_prompt(
        {
            "id": "web_custom",
            "category": "web",
            "name": "Caso propio",
            "capability": "web",
            "tags": ["web", "readonly"],
            "prompt": "Consultá una fuente y resumila.",
            "must_match": ["fuente"],
        }
    )
    case = next(item for item in store.prompts() if item["id"] == "web_custom")
    assert case["category"] == "web"
    assert case["tags"] == ["web", "readonly"]


def test_healthcheck_evaluation_requires_all_capability_signals():
    item = {"must_match": [r"fuente", r"IA"]}
    result = evaluate(item, "Encontré una fuente sobre IA", 0.4)
    assert result["passed"] is True
    failed = evaluate(item, "No pude consultar internet", 0.4)
    assert failed["passed"] is False
    assert failed["missing"] == [r"fuente", r"IA"]


def test_external_healthchecks_require_mcp_grounding():
    assert requires_mcp({"category": "mcp_google_calendar"}) is True
    assert requires_mcp({"category": "calendar"}) is True
    assert requires_mcp({"category": "reasoning"}) is False


def test_healthcheck_run_history_is_json_safe():
    memory = Memory(":memory:")
    store = HealthcheckStore(memory)
    store.save_run(
        "run-1",
        "web_search",
        "fuente IA",
        {"passed": True},
        0.2,
        request="Buscá una fuente",
        status="passed",
        status_code=200,
        model="judge:test",
        mcps=[{"server": "web", "tool": "search"}],
        trace=[{"phase": "completed", "at_seconds": 0.2}],
    )
    history = store.history()
    assert history[0]["run_id"] == "run-1"
    assert history[0]["status"] == "passed"
    assert history[0]["model"] == "judge:test"
    assert history[0]["mcps"][0]["tool"] == "search"
    assert history[0]["trace"][0]["phase"] == "completed"
    assert json.loads(json.dumps(history, ensure_ascii=False))[0]["evaluation"]["passed"] is True


def test_orphaned_healthcheck_batches_are_marked_interrupted():
    memory = Memory(":memory:")
    store = HealthcheckStore(memory)
    store.begin_batch("orphaned-run", ["web_search"])
    store.mark_batch_running("orphaned-run", "web_search")

    store.recover_orphaned_batches(set())

    assert store.batch("orphaned-run")["status"] == "interrupted"
    assert store.active_batches() == []


def test_latest_result_is_selected_per_prompt():
    memory = Memory(":memory:")
    store = HealthcheckStore(memory)
    store.save_run("run-1", "same_prompt", "old", {"passed": False}, 1.0, status="failed")
    store.save_run("run-2", "same_prompt", "new", {"passed": True}, 2.0, status="passed")
    latest = store.latest_results()
    assert len([item for item in latest if item["prompt_id"] == "same_prompt"]) == 1
    assert next(item for item in latest if item["prompt_id"] == "same_prompt")["response"] == "new"


def test_concurrent_catalog_reads_do_not_break_shared_sqlite_connection():
    memory = Memory(":memory:")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: len(HealthcheckStore(memory).prompts()), range(12)))
    assert results and all(value == len(HEALTHCHECK_PROMPTS) for value in results)


def test_llm_judge_never_approves_explicit_access_failure():
    result = llm_judge(
        {"name": "fotos", "prompt": "Buscá fotos", "must_match": ["foto"]}, "No pude acceder a Google Drive."
    )
    assert result["passed"] is False
    assert result["source"] == "guard"


@patch("urllib.request.urlopen")
def test_llm_judge_uses_semantic_verdict_and_score(mock_urlopen):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {
            "response": json.dumps(
                {
                    "passed": False,
                    "score": 0.2,
                    "issues": ["No aporta datos reales"],
                    "rationale": "Solo explica una limitación.",
                }
            )
        }
    ).encode()
    mock_urlopen.return_value = response
    result = llm_judge(
        {"name": "calendario", "prompt": "Decime mi próximo evento", "must_match": ["evento"]},
        "Podés consultar el calendario desde la configuración.",
    )
    assert result["passed"] is False
    assert result["source"] == "llm"
    assert result["issues"] == ["No aporta datos reales"]


@patch("urllib.request.urlopen")
def test_llm_judge_does_not_require_mcp_for_conceptual_cases(mock_urlopen):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {"response": json.dumps({"passed": True, "score": 0.9, "issues": [], "rationale": "Explicación completa."})}
    ).encode()
    mock_urlopen.return_value = response
    llm_judge(
        {
            "category": "reasoning",
            "name": "timeout",
            "prompt": "Explicá qué significa un timeout",
            "must_match": ["tiempo"],
        },
        "Un timeout es un límite de tiempo para completar una tarea.",
    )
    request_body = mock_urlopen.call_args.args[0].data.decode()
    assert "no exijas evidencia de MCP" in json.loads(request_body)["prompt"]
