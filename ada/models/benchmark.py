"""Model benchmark, prompt testing suite and resource telemetry utilities."""

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ada.models.benchmark")

try:
    import psutil
except Exception:
    psutil = None


def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _find_project_root()
BENCHMARK_PATH = PROJECT_ROOT / "models" / "benchmarks.json"

BENCHMARK_PROMPTS = {
    "quick": {
        "title": "Respuesta Rápida",
        "description": "Prueba de latencia y concisión básica.",
        "prompt": "Explica brevemente en dos oraciones qué es un agente autónomo local.",
    },
    "reasoning": {
        "title": "Razonamiento Lógico",
        "description": "Cálculo aritmético y deducción estructurada.",
        "prompt": "Si tengo 3 manzanas y compro 2 más, pero regalo 1 y como otra, ¿cuántas manzanas me quedan? Responde paso a paso de forma clara.",
    },
    "json": {
        "title": "Estructuración JSON",
        "description": "Generación estricta de JSON válido con esquema de tareas.",
        "prompt": "Devuelve un objeto JSON válido con una clave 'tareas' que contenga una lista de 3 tareas recomendadas para organizar archivos, cada una con 'id', 'titulo' y 'prioridad' (alta/media/baja). Solo JSON sin texto adicional.",
    },
    "planning": {
        "title": "Planificación y Coordinación",
        "description": "Desglose de workflow paso a paso para agentes.",
        "prompt": "Genera un plan de 4 pasos secuenciales para organizar una carpeta de fotografías de un evento, detectando duplicados y aplicando metadata XMP.",
    },
    "coding": {
        "title": "Generación de Código",
        "description": "Escritura de código limpio y eficiente sin librerías externas.",
        "prompt": "Escribe una función en Python llamada calcular_estadisticas(numeros) que calcule y retorne la media, varianza y desviación estándar de una lista sin importar librerías externas.",
    },
}


def _get_resource_snapshot() -> Dict[str, Any]:
    """Capture current system hardware resource utilization."""
    ram_gb = 0.0
    ram_used_gb = 0.0
    ram_available_gb = 0.0
    ram_percent = 0.0
    cpu_percent = 0.0

    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            ram_gb = round(vm.total / (1024**3), 2)
            ram_used_gb = round(vm.used / (1024**3), 2)
            ram_available_gb = round(vm.available / (1024**3), 2)
            ram_percent = round(vm.percent, 1)
            cpu_percent = round(psutil.cpu_percent(interval=None), 1)
        except Exception:
            pass

    vram_gb = 0.0
    gpu_backend = "cpu"
    try:
        import torch

        if bool(getattr(torch, "cuda", None)) and torch.cuda.is_available():
            gpu_backend = "cuda"
            vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
        elif getattr(torch, "backends", None) and torch.backends.mps.is_available():
            gpu_backend = "mps"
    except Exception:
        pass

    if vram_gb == 0.0:
        try:
            import subprocess

            smi = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if smi.returncode == 0 and smi.stdout.strip():
                mb = float(smi.stdout.strip().splitlines()[0])
                vram_gb = round(mb / 1024.0, 1)
                gpu_backend = "cuda"
        except Exception:
            pass

    return {
        "cpu_percent": cpu_percent,
        "ram_gb": ram_gb,
        "ram_used_gb": ram_used_gb,
        "ram_available_gb": ram_available_gb,
        "ram_percent": ram_percent,
        "vram_gb": vram_gb,
        "gpu_backend": gpu_backend,
        "cpu_cores": os.cpu_count() or 1,
    }


class ModelBenchmark:
    """Runs single or full-suite prompt benchmarks with latency, throughput and hardware metrics."""

    def __init__(self, endpoint: str = "http://127.0.0.1:11434"):
        self.endpoint = endpoint.rstrip("/")

    def get_prompt_catalog(self) -> Dict[str, Any]:
        """Return available prompt presets for the UI."""
        return {
            key: {
                "key": key,
                "title": data["title"],
                "description": data["description"],
                "prompt": data["prompt"],
            }
            for key, data in BENCHMARK_PROMPTS.items()
        }

    def run(
        self,
        model_name: str,
        prompt_key: str = "quick",
        custom_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a single prompt benchmark measuring timing and system resources."""
        if custom_prompt and custom_prompt.strip():
            prompt_text = custom_prompt.strip()
            prompt_title = "Prompt Personalizado"
        else:
            preset = BENCHMARK_PROMPTS.get(prompt_key, BENCHMARK_PROMPTS["quick"])
            prompt_text = preset["prompt"]
            prompt_title = preset["title"]

        req_options = {"temperature": 0.2, "num_predict": 256}
        if options:
            req_options.update(options)

        payload = {
            "model": model_name,
            "prompt": prompt_text,
            "stream": False,
            "options": req_options,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        res_before = _get_resource_snapshot()
        start_time = time.monotonic()

        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                raw_json = resp.read().decode("utf-8")
                total_time = round(time.monotonic() - start_time, 3)
                result = json.loads(raw_json)

            res_after = _get_resource_snapshot()

            eval_count = int(result.get("eval_count", 0) or 0)
            prompt_eval_count = int(result.get("prompt_eval_count", 0) or 0)
            eval_duration_ns = int(result.get("eval_duration", 0) or 0)
            prompt_eval_duration_ns = int(result.get("prompt_eval_duration", 0) or 0)

            tokens_per_sec = 0.0
            if eval_duration_ns > 0 and eval_count > 0:
                tokens_per_sec = round(eval_count / (eval_duration_ns / 1e9), 2)
            elif total_time > 0 and eval_count > 0:
                tokens_per_sec = round(eval_count / total_time, 2)

            ttft_ms = round(prompt_eval_duration_ns / 1e6, 2) if prompt_eval_duration_ns > 0 else None

            # Calculate RAM delta in MB
            ram_delta_mb = round((res_after["ram_used_gb"] - res_before["ram_used_gb"]) * 1024, 1)

            benchmark_res = {
                "ok": True,
                "model": model_name,
                "prompt_key": prompt_key,
                "prompt_title": prompt_title,
                "prompt": prompt_text,
                "tokens_per_second": tokens_per_sec,
                "ttft_ms": ttft_ms,
                "eval_count": eval_count,
                "prompt_eval_count": prompt_eval_count,
                "total_tokens": eval_count + prompt_eval_count,
                "total_time_seconds": total_time,
                "total_time_s": total_time,
                "response": result.get("response", ""),
                "response_text": result.get("response", ""),
                "resources": {
                    "cpu_percent": res_after["cpu_percent"],
                    "ram_used_gb": res_after["ram_used_gb"],
                    "ram_total_gb": res_after["ram_gb"],
                    "ram_percent": res_after["ram_percent"],
                    "ram_delta_mb": ram_delta_mb,
                    "vram_gb": res_after["vram_gb"],
                    "gpu_backend": res_after["gpu_backend"],
                    "cpu_cores": res_after["cpu_cores"],
                },
            }

            self._save_benchmark(benchmark_res)
            return benchmark_res

        except Exception as err:
            total_time = round(time.monotonic() - start_time, 3)
            res_after = _get_resource_snapshot()
            logger.warning("benchmark_run_failed model=%s error=%s", model_name, err)
            return {
                "ok": False,
                "model": model_name,
                "prompt_key": prompt_key,
                "prompt_title": prompt_title,
                "prompt": prompt_text,
                "error": str(err),
                "total_time_seconds": total_time,
                "total_time_s": total_time,
                "resources": res_after,
            }

    def run_suite(
        self,
        model_name: str,
        prompt_keys: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a full test suite of prompts sequentially and produce summary metrics."""
        keys = prompt_keys or list(BENCHMARK_PROMPTS.keys())
        results: List[Dict[str, Any]] = []

        suite_start = time.monotonic()
        total_tokens = 0
        total_eval_tokens = 0
        tps_list: List[float] = []
        ttft_list: List[float] = []
        cpu_readings: List[float] = []
        ram_readings: List[float] = []

        for key in keys:
            res = self.run(model_name, prompt_key=key, options=options)
            results.append(res)
            if res.get("ok"):
                tps = res.get("tokens_per_second", 0.0)
                if tps > 0:
                    tps_list.append(tps)
                ttft = res.get("ttft_ms")
                if ttft is not None:
                    ttft_list.append(ttft)
                total_tokens += res.get("total_tokens", 0)
                total_eval_tokens += res.get("eval_count", 0)

            rec = res.get("resources", {})
            if rec.get("cpu_percent") is not None:
                cpu_readings.append(rec["cpu_percent"])
            if rec.get("ram_used_gb") is not None:
                ram_readings.append(rec["ram_used_gb"])

        suite_duration = round(time.monotonic() - suite_start, 3)
        successful = sum(1 for r in results if r.get("ok"))
        failed = len(results) - successful

        avg_tps = round(sum(tps_list) / len(tps_list), 2) if tps_list else 0.0
        avg_ttft = round(sum(ttft_list) / len(ttft_list), 1) if ttft_list else None
        avg_cpu = round(sum(cpu_readings) / len(cpu_readings), 1) if cpu_readings else 0.0
        peak_cpu = max(cpu_readings) if cpu_readings else 0.0
        avg_ram = round(sum(ram_readings) / len(ram_readings), 2) if ram_readings else 0.0
        peak_ram = max(ram_readings) if ram_readings else 0.0

        latest_resources = _get_resource_snapshot()

        return {
            "ok": successful > 0,
            "suite_run": True,
            "model": model_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "results": results,
            "summary": {
                "total_prompts": len(results),
                "successful_prompts": successful,
                "failed_prompts": failed,
                "total_duration_s": suite_duration,
                "avg_tokens_per_second": avg_tps,
                "avg_ttft_ms": avg_ttft,
                "total_tokens_generated": total_eval_tokens,
                "total_tokens_processed": total_tokens,
                "avg_cpu_percent": avg_cpu,
                "peak_cpu_percent": peak_cpu,
                "avg_ram_used_gb": avg_ram,
                "peak_ram_used_gb": peak_ram,
            },
            "resources": latest_resources,
        }

    def _save_benchmark(self, result: Dict[str, Any]) -> None:
        try:
            history = []
            if BENCHMARK_PATH.is_file():
                with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    history = data.get("history", [])

            history.append(
                {
                    "model": result.get("model"),
                    "prompt_key": result.get("prompt_key"),
                    "prompt_title": result.get("prompt_title"),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "tokens_per_second": result.get("tokens_per_second"),
                    "ttft_ms": result.get("ttft_ms"),
                    "total_tokens": result.get("eval_count"),
                    "duration_seconds": result.get("total_time_seconds"),
                    "cpu_percent": result.get("resources", {}).get("cpu_percent"),
                    "ram_used_gb": result.get("resources", {}).get("ram_used_gb"),
                }
            )

            BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
                json.dump({"version": "1.1.0", "history": history[-100:]}, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.debug("save_benchmark_error error=%s", exc)
