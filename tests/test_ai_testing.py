import json
from pathlib import Path

from ai_testing.runner import evaluate, safe_case

def test_catalog_contains_only_safe_cases():
    cases = json.loads((Path(__file__).parents[1] / "ai_testing" / "prompts.json").read_text())
    assert cases and all(safe_case(case) for case in cases)

def test_mutating_prompt_is_blocked():
    assert not safe_case({"prompt": "borrá todos los archivos"})

def test_evaluation_detects_missing_expected_content():
    result = evaluate({"must_contain": ["XML", "RAW", "JPG"], "max_seconds": 5}, {"reply": "Hay fotos JPG"}, 1)
    assert result["passed"] is False
    assert "XML" in result["missing"]

def test_evaluation_requires_human_photo_summary():
    case = {"must_match": [r"\d+\s+fotos?\s+aceptadas", r"(exportadas|sin exportar)"]}
    result = evaluate(case, {"reply": "Encontré las carpetas Originales, Videos y JPG"}, 1)
    assert result["passed"] is False
    assert any("patrón" in item for item in result["missing"])
