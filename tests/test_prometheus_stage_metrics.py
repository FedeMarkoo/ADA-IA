import time
from prometheus_client import generate_latest

from ada.infrastructure.prometheus_metrics import (
    REGISTRY,
    PIPELINE_STAGE_DURATION,
    PIPELINE_STAGE_LAST,
    measure_stage,
    record_stage_duration,
)
from ada.infrastructure.persistence.sqlite import Memory
from ada.application.context_manager import ContextManager
from ada.application.services.prompts import PromptBuilder
from ada.application.services.folder_resolver import FolderResolver


def test_measure_stage_context_manager():
    with measure_stage("test_stage_ok"):
        time.sleep(0.005)

    last_val = PIPELINE_STAGE_LAST.labels(stage="test_stage_ok")._value.get()
    assert last_val >= 0.004

    sum_val = PIPELINE_STAGE_DURATION.labels(stage="test_stage_ok", status="ok")._sum.get()
    assert sum_val >= 0.004


def test_measure_stage_error_handling():
    try:
        with measure_stage("test_stage_err"):
            raise ValueError("boom")
    except ValueError:
        pass

    err_sum = PIPELINE_STAGE_DURATION.labels(stage="test_stage_err", status="error")._sum.get()
    assert err_sum >= 0.0


def test_record_stage_duration():
    record_stage_duration("test_manual_stage", 0.042, status="ok")
    last_val = PIPELINE_STAGE_LAST.labels(stage="test_manual_stage")._value.get()
    assert abs(last_val - 0.042) < 1e-5


def test_context_manager_instruments_pipeline(tmp_path):
    mem = Memory(str(tmp_path / "mem.db"))
    cm = ContextManager(memory=mem)
    cm.build(conversation_id="test_conv", query="testing memory")

    last_val = PIPELINE_STAGE_LAST.labels(stage="context_build")._value.get()
    assert last_val >= 0.0
    sum_val = PIPELINE_STAGE_DURATION.labels(stage="context_build", status="ok")._sum.get()
    assert sum_val >= 0.0


def test_memory_retrieval_instruments_pipeline(tmp_path):
    mem = Memory(str(tmp_path / "mem.db"))
    mem_id = mem.add_memory_record("Record 1 about project architecture", summary="Architecture summary")
    
    candidates = mem.retrieve_memory_candidates("architecture", limit=5)
    assert len(candidates) >= 1
    assert PIPELINE_STAGE_DURATION.labels(stage="memory_candidates_retrieval", status="ok")._sum.get() >= 0.0

    records = mem.memory_records_by_ids([mem_id])
    assert len(records) == 1
    assert PIPELINE_STAGE_DURATION.labels(stage="memory_records_fetch", status="ok")._sum.get() >= 0.0

    search_res = mem.search_text("architecture")
    assert len(search_res) >= 1
    assert PIPELINE_STAGE_DURATION.labels(stage="memory_search", status="ok")._sum.get() >= 0.0


def test_prompt_builder_instruments_pipeline(tmp_path):
    mem = Memory(str(tmp_path / "mem.db"))
    pb = PromptBuilder(mem)
    prompt = pb.task({"prompt": "Hola ADA"})
    assert "ADA" in prompt
    assert PIPELINE_STAGE_DURATION.labels(stage="prompt_builder", status="ok")._sum.get() >= 0.0


def test_folder_resolver_instruments_pipeline(tmp_path):
    fr = FolderResolver(config={})
    fr.resolve("fotos")
    assert PIPELINE_STAGE_DURATION.labels(stage="folder_resolver", status="ok")._sum.get() >= 0.0


def test_prometheus_export_includes_pipeline_metrics():
    output = generate_latest(REGISTRY).decode("utf-8")
    assert "ada_pipeline_stage_duration_seconds" in output
    assert "ada_pipeline_stage_last_seconds" in output
