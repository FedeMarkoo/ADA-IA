"""Model benchmark and latency testing utilities with persistence to models/benchmarks.json."""

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _find_project_root()
BENCHMARK_PATH = PROJECT_ROOT / "models" / "benchmarks.json"

BENCHMARK_PROMPTS = {
    "quick": "Explica brevemente en dos oraciones qué es un agente autónomo local.",
    "reasoning": "Si tengo 3 manzanas y compro 2 más, pero regalo 1 y como otra, ¿cuántas manzanas me quedan? Responde paso a paso.",
    "json": "Devuelve un JSON con 3 tareas recomendadas para organizar fotos digitales.",
}


class ModelBenchmark:
    """Runs a live prompt benchmark against an Ollama model to evaluate performance."""

    def __init__(self, endpoint: str = "http://127.0.0.1:11434"):
        self.endpoint = endpoint.rstrip("/")

    def run(self, model_name: str, prompt_key: str = "quick") -> Dict[str, Any]:
        prompt = BENCHMARK_PROMPTS.get(prompt_key, BENCHMARK_PROMPTS["quick"])
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 128},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start_time = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=45.0) as resp:
                raw_json = resp.read().decode("utf-8")
                total_time = round(time.monotonic() - start_time, 3)
                result = json.loads(raw_json)

            eval_count = result.get("eval_count", 0)
            eval_duration_ns = result.get("eval_duration", 0)
            prompt_eval_duration_ns = result.get("prompt_eval_duration", 0)

            tokens_per_sec = 0.0
            if eval_duration_ns > 0 and eval_count > 0:
                tokens_per_sec = round(eval_count / (eval_duration_ns / 1e9), 2)
            elif total_time > 0 and eval_count > 0:
                tokens_per_sec = round(eval_count / total_time, 2)

            ttft_ms = round(prompt_eval_duration_ns / 1e6, 2) if prompt_eval_duration_ns > 0 else None

            benchmark_res = {
                "ok": True,
                "model": model_name,
                "prompt": prompt,
                "tokens_per_second": tokens_per_sec,
                "ttft_ms": ttft_ms,
                "eval_count": eval_count,
                "total_time_seconds": total_time,
                "response_text": result.get("response", ""),
            }

            self._save_benchmark(benchmark_res)
            return benchmark_res
        except Exception as err:
            return {
                "ok": False,
                "model": model_name,
                "error": str(err),
            }

    def _save_benchmark(self, result: Dict[str, Any]) -> None:
        try:
            history = []
            if BENCHMARK_PATH.is_file():
                with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    history = data.get("history", [])

            history.append({
                "model": result.get("model"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tokens_per_second": result.get("tokens_per_second"),
                "ttft_ms": result.get("ttft_ms"),
                "total_tokens": result.get("eval_count"),
                "duration_seconds": result.get("total_time_seconds"),
            })

            BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
                json.dump({"version": "1.0.0", "history": history[-50:]}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
