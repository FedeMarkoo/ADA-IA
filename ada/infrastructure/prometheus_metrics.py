"""Prometheus instrumentation shared by the ADA process.

The registry is deliberately local to ADA so importing the web application in
tests or embedding it in another process does not mutate prometheus' global
registry. Prometheus scrapes this process directly; no local polling worker or
SQLite time-series database is needed.
"""

import json
import os
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import psutil
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, ProcessCollector, generate_latest

REGISTRY = CollectorRegistry(auto_describe=True)
ProcessCollector(registry=REGISTRY)

PIPELINE_STAGE_DURATION = Histogram(
    "ada_pipeline_stage_duration_seconds",
    "Duration of pipeline stages and internal processing layers in seconds.",
    ("stage", "status"),
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)
PIPELINE_STAGE_LAST = Gauge(
    "ada_pipeline_stage_last_seconds",
    "Latest execution duration of pipeline stages and layers in seconds.",
    ("stage",),
    registry=REGISTRY,
)

REQUESTS = Counter(
    "ada_http_requests_total",
    "Total HTTP requests handled by ADA.",
    ("method", "route", "status"),
    registry=REGISTRY,
)
REQUEST_LATENCY = Histogram(
    "ada_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ("method", "route"),
    registry=REGISTRY,
)
EVENTS = Counter(
    "ada_events_total",
    "ADA application events.",
    ("metric", "tags"),
    registry=REGISTRY,
)
RESPONSES = Counter(
    "ada_responses_total",
    "ADA responses by source and result.",
    ("source", "status"),
    registry=REGISTRY,
)
OPERATIONS = Histogram(
    "ada_operation_duration_seconds",
    "Duration of ADA instrumented operations.",
    ("metric", "tags"),
    registry=REGISTRY,
)
MCP_EXECUTIONS = Counter(
    "ada_mcp_tool_executions_total",
    "MCP tool executions by MCP server, tool and result status.",
    ("mcp", "tool", "status"),
    registry=REGISTRY,
)
MCP_DURATION = Histogram(
    "ada_mcp_tool_duration_seconds",
    "MCP tool execution duration in seconds.",
    ("mcp", "tool", "status"),
    registry=REGISTRY,
)
MCP_IN_FLIGHT = Gauge(
    "ada_mcp_tool_in_flight",
    "MCP tool calls currently running.",
    ("mcp", "tool"),
    registry=REGISTRY,
)
MCP_SERVER_IN_FLIGHT = Gauge(
    "ada_mcp_in_flight",
    "MCP calls currently running per server.",
    ("mcp",),
    registry=REGISTRY,
)
MCP_RUNNING = Gauge(
    "ada_mcp_running",
    "Whether an MCP is enabled and available to execute (1/0).",
    ("mcp",),
    registry=REGISTRY,
)
MCP_TOOL_ENABLED = Gauge(
    "ada_mcp_tool_enabled",
    "Whether an MCP tool is enabled (1/0).",
    ("mcp", "tool"),
    registry=REGISTRY,
)
MCP_MEMORY = Gauge(
    "ada_mcp_memory_bytes",
    "Resident memory attributed to an MCP process. In-process MCPs share ADA memory.",
    ("mcp",),
    registry=REGISTRY,
)
MCP_CPU = Counter(
    "ada_mcp_cpu_seconds_total",
    "Process CPU time observed while executing MCP tools.",
    ("mcp", "tool"),
    registry=REGISTRY,
)
OLLAMA_EXECUTIONS = Counter(
    "ada_ollama_model_executions_total",
    "Ollama model calls by model and result status.",
    ("model", "status"),
    registry=REGISTRY,
)
OLLAMA_DURATION = Histogram(
    "ada_ollama_model_duration_seconds",
    "Ollama model call duration in seconds.",
    ("model", "status"),
    registry=REGISTRY,
)
OLLAMA_IN_FLIGHT = Gauge(
    "ada_ollama_model_in_flight",
    "Ollama calls currently running by model.",
    ("model",),
    registry=REGISTRY,
)
OLLAMA_MODEL_MEMORY = Gauge(
    "ada_ollama_model_memory_bytes",
    "Resident process memory attributed to each loaded Ollama model.",
    ("model",),
    registry=REGISTRY,
)
OLLAMA_MODEL_VRAM = Gauge(
    "ada_ollama_model_vram_bytes",
    "VRAM reported by Ollama for each loaded model.",
    ("model",),
    registry=REGISTRY,
)
OLLAMA_MODEL_CPU = Gauge(
    "ada_ollama_model_cpu_usage_ratio",
    "CPU usage ratio attributed to each loaded Ollama model runner.",
    ("model",),
    registry=REGISTRY,
)
OLLAMA_MODEL_LOADED = Gauge(
    "ada_ollama_model_loaded",
    "Whether an Ollama model is currently loaded (1/0).",
    ("model",),
    registry=REGISTRY,
)
ADA_ACTIVE = Gauge(
    "ada_active_operations",
    "ADA operations currently in progress.",
    ("operation",),
    registry=REGISTRY,
)
SYSTEM_MEMORY = Gauge(
    "ada_system_memory_bytes",
    "System memory in bytes.",
    ("state",),
    registry=REGISTRY,
)
SYSTEM_CPU = Gauge(
    "ada_system_cpu_usage_ratio",
    "System CPU usage ratio between 0 and 1.",
    registry=REGISTRY,
)
SYSTEM_GPU = Gauge(
    "ada_system_gpu_usage_ratio",
    "GPU utilization ratio by device between 0 and 1.",
    ("gpu",),
    registry=REGISTRY,
)
SYSTEM_GPU_MEMORY = Gauge(
    "ada_system_gpu_memory_bytes",
    "GPU memory in bytes, when reported by nvidia-smi.",
    ("gpu", "state"),
    registry=REGISTRY,
)
SYSTEM_GPU_AVAILABLE = Gauge(
    "ada_system_gpu_available",
    "Whether a GPU was detected through nvidia-smi (1/0).",
    registry=REGISTRY,
)
ADA_PROCESS_MEMORY = Gauge(
    "ada_process_memory_bytes",
    "ADA process resident memory in bytes.",
    registry=REGISTRY,
)
ADA_PROCESS_CPU = Gauge(
    "ada_process_cpu_usage_ratio",
    "ADA process CPU usage ratio between 0 and 1.",
    registry=REGISTRY,
)
ADA_PROCESS_UPTIME = Gauge(
    "ada_process_uptime_seconds",
    "ADA process uptime in seconds.",
    registry=REGISTRY,
)
COMPONENT_MEMORY = Gauge(
    "ada_component_memory_bytes",
    "Resident memory by detected process component.",
    ("component",),
    registry=REGISTRY,
)
COMPONENT_CPU = Gauge(
    "ada_component_cpu_usage_ratio",
    "CPU usage ratio by detected process component.",
    ("component",),
    registry=REGISTRY,
)
COMPONENT_RUNNING = Gauge(
    "ada_component_running",
    "Whether a detected process component is running (1/0).",
    ("component",),
    registry=REGISTRY,
)
LLM_TOKEN_USAGE = Gauge(
    "ada_llm_tokens",
    "Latest LLM token usage split by context component.",
    ("component",),
    registry=REGISTRY,
)
LLM_TOKENS_TOTAL = Counter(
    "ada_llm_tokens_consumed",
    "Cumulative LLM tokens consumed by context component.",
    ("component",),
    registry=REGISTRY,
)
HEALTHCHECK_RUNS = Counter(
    "ada_healthcheck_runs_total",
    "Total healthcheck and prompt test executions by category, capability and status.",
    ("category", "capability", "status"),
    registry=REGISTRY,
)
HEALTHCHECK_DURATION = Histogram(
    "ada_healthcheck_duration_seconds",
    "Duration of individual healthcheck prompt test executions in seconds.",
    ("category", "capability", "status"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)
HEALTHCHECK_JUDGE_SCORE = Histogram(
    "ada_healthcheck_judge_score",
    "Evaluation score awarded by AI judge (0.0 to 1.0).",
    ("category", "model"),
    buckets=(0.0, 0.25, 0.5, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0),
    registry=REGISTRY,
)
HEALTHCHECK_BATCH_RUNS = Counter(
    "ada_healthcheck_batch_runs_total",
    "Healthcheck batch runs by lifecycle status (started, completed, interrupted).",
    ("status",),
    registry=REGISTRY,
)
HEALTHCHECK_ACTIVE_BATCHES = Gauge(
    "ada_healthcheck_active_batches",
    "Number of currently running healthcheck batches.",
    registry=REGISTRY,
)
HEALTHCHECK_PASS_RATE = Gauge(
    "ada_healthcheck_last_pass_rate_ratio",
    "Latest observed pass rate ratio per category (0.0 to 1.0).",
    ("category",),
    registry=REGISTRY,
)
ROUTER_DECISIONS = Counter(
    "ada_router_decisions_total",
    "Intent routing decisions by action, intent type and execution status.",
    ("action", "intent_type", "status"),
    registry=REGISTRY,
)
ROUTER_CONFIDENCE = Histogram(
    "ada_router_confidence_score",
    "Confidence score distribution of routing decisions.",
    ("action",),
    buckets=(0.0, 0.2, 0.4, 0.6, 0.75, 0.85, 0.95, 1.0),
    registry=REGISTRY,
)
ROUTER_ERRORS = Counter(
    "ada_router_errors_total",
    "Routing errors by error type.",
    ("error_type",),
    registry=REGISTRY,
)
ROUTER_FALLBACKS = Counter(
    "ada_router_fallbacks_total",
    "Router fallback events by trigger.",
    ("trigger",),
    registry=REGISTRY,
)
LLM_GENERATION_SPEED = Histogram(
    "ada_llm_generation_speed_tokens_per_second",
    "LLM generation throughput in tokens per second.",
    ("model",),
    buckets=(1.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0, 75.0, 100.0),
    registry=REGISTRY,
)
LLM_CONTEXT_SATURATION = Gauge(
    "ada_llm_context_saturation_ratio",
    "Ratio of LLM context window used (0.0 to 1.0).",
    ("model",),
    registry=REGISTRY,
)
LLM_RETRIES = Counter(
    "ada_llm_retries_total",
    "LLM call retries and fallbacks by model and reason.",
    ("model", "reason"),
    registry=REGISTRY,
)
SQLITE_QUERIES = Counter(
    "ada_sqlite_queries_total",
    "SQLite database operations by table and operation type.",
    ("table", "operation"),
    registry=REGISTRY,
)
SQLITE_QUERY_DURATION = Histogram(
    "ada_sqlite_query_duration_seconds",
    "Duration of SQLite database operations in seconds.",
    ("operation",),
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    registry=REGISTRY,
)
MEMORY_REFINER_RUNS = Counter(
    "ada_memory_refiner_runs_total",
    "Memory refiner execution cycles by status.",
    ("status",),
    registry=REGISTRY,
)
MEMORY_REFINER_FACTS = Counter(
    "ada_memory_refiner_extracted_facts_total",
    "Total facts extracted from conversations by memory refiner.",
    registry=REGISTRY,
)
TELEGRAM_MESSAGES = Counter(
    "ada_telegram_messages_total",
    "Telegram messages processed by direction (inbound, outbound) and status.",
    ("direction", "status"),
    registry=REGISTRY,
)
TELEGRAM_LATENCY = Histogram(
    "ada_telegram_latency_seconds",
    "End-to-end processing latency for Telegram messages in seconds.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)
TELEGRAM_POLLING_ERRORS = Counter(
    "ada_telegram_polling_errors_total",
    "Telegram polling or transport errors by type.",
    ("error_type",),
    registry=REGISTRY,
)
SYSTEM_ERRORS = Counter(
    "ada_system_errors_total",
    "System and component errors by component and error class.",
    ("component", "error_class"),
    registry=REGISTRY,
)
UP = Gauge("ada_up", "Whether the ADA web process is alive.", registry=REGISTRY)
UP.set(1)

_process = psutil.Process(os.getpid())
_process_started = time.time()
_observed_ollama_models = set()
TOKEN_COMPONENTS = ("memory", "tools", "tool_response", "system", "prompt", "response", "libre", "total")
DEFAULT_CONTEXT_WINDOW = 4096


def estimate_token_count(value) -> int:
    """Estimate tokens without requiring a provider-specific tokenizer."""
    return max(0, (len(str(value or "")) + 3) // 4)


def set_llm_token_usage(usage=None, response=None, max_context=None) -> dict:
    """Publish the latest request breakdown and return normalized values."""
    values = {component: 0 for component in TOKEN_COMPONENTS}
    for component in ("memory", "tools", "tool_response", "system", "prompt"):
        if usage and component in usage:
            values[component] = max(0, int(usage[component] or 0))
    if usage and usage.get("response"):
        values["response"] = max(0, int(usage["response"]))
    if response is not None:
        values["response"] = estimate_token_count(response)

    used_components = ("memory", "tools", "tool_response", "system", "prompt", "response")
    values["total"] = sum(values[component] for component in used_components)

    ctx_limit = int(max_context or (usage.get("num_ctx") if usage else None) or DEFAULT_CONTEXT_WINDOW)
    values["libre"] = max(0, ctx_limit - values["total"])

    for component, value in values.items():
        LLM_TOKEN_USAGE.labels(component=component).set(value)
        if response is not None and value > 0 and component != "libre":
            LLM_TOKENS_TOTAL.labels(component=component).inc(value)
    return values


def reset_llm_token_usage(max_context=None) -> None:
    """Reset the active LLM token gauge to 0 and restore libre to full context capacity."""
    for component in ("memory", "tools", "tool_response", "system", "prompt", "response", "total"):
        LLM_TOKEN_USAGE.labels(component=component).set(0)
    ctx_limit = int(max_context or DEFAULT_CONTEXT_WINDOW)
    LLM_TOKEN_USAGE.labels(component="libre").set(ctx_limit)


# Initialize default gauges and counters
reset_llm_token_usage()
for _c in ("memory", "tools", "tool_response", "system", "prompt", "response", "total"):
    LLM_TOKENS_TOTAL.labels(component=_c).inc(0)


@contextmanager
def measure_stage(stage: str):
    """Context manager to record duration of a pipeline stage in Prometheus."""
    started = time.monotonic()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = max(0.0, time.monotonic() - started)
        try:
            PIPELINE_STAGE_DURATION.labels(stage=stage, status=status).observe(duration)
            PIPELINE_STAGE_LAST.labels(stage=stage).set(duration)
        except Exception:
            pass


def record_stage_duration(stage: str, duration: float, status: str = "ok") -> None:
    """Explicitly record a duration for a pipeline stage."""
    try:
        sec = max(0.0, float(duration))
        PIPELINE_STAGE_DURATION.labels(stage=stage, status=status).observe(sec)
        PIPELINE_STAGE_LAST.labels(stage=stage).set(sec)
    except Exception:
        pass



def _ollama_manifest_path(model: str, models_root: str = "") -> Path:
    """Resolve an Ollama model name to its local manifest path."""
    reference = str(model or "").split("@", 1)[0].strip("/")
    parts = reference.split("/") if reference else []
    if not parts:
        return Path("/__missing_ollama_manifest__")

    last = parts.pop()
    if ":" in last:
        repository, tag = last.rsplit(":", 1)
    else:
        repository, tag = last, "latest"

    if parts and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        host = parts.pop(0)
    else:
        host = "registry.ollama.ai"
    namespace = parts or ["library"]
    root = Path(models_root or os.environ.get("OLLAMA_MODELS", "~/.ollama/models")).expanduser()
    return root.joinpath("manifests", host, *namespace, repository, tag)


def _ollama_model_blob_digest(model: str, models_root: str = "") -> str:
    """Return the model-layer digest used in an Ollama runner command line."""
    try:
        manifest = json.loads(_ollama_manifest_path(model, models_root).read_text(encoding="utf-8"))
        for layer in manifest.get("layers", []):
            if str(layer.get("mediaType", "")).endswith(".model"):
                return str(layer.get("digest", "")).removeprefix("sha256:")
    except (OSError, ValueError, TypeError):
        pass
    return ""


def _running_ollama_models():
    endpoint = os.environ.get("ADA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        request = urllib.request.Request(endpoint + "/api/ps", method="GET")
        with urllib.request.urlopen(request, timeout=1.0) as response:
            return json.loads(response.read().decode("utf-8")).get("models", [])
    except (OSError, ValueError):
        return []


def _gpu_stats():
    """Read GPU utilization from NVIDIA CLI or Intel iGPU frequency telemetry."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0:
        rows = []
        for line in result.stdout.splitlines():
            values = [value.strip() for value in line.split(",")]
            if len(values) != 3:
                continue
            try:
                rows.append(tuple(float(value) for value in values))
            except ValueError:
                continue
        if rows:
            utilization, memory_used, memory_total = zip(*rows)
            return {
                "gpus": [
                    {
                        "name": f"nvidia:{index}",
                        "usage_ratio": value / 100.0,
                        "memory_used": int(used * 1024 * 1024),
                        "memory_total": int(total * 1024 * 1024),
                    }
                    for index, (value, used, total) in enumerate(rows)
                ]
            }

    # Intel integrated GPUs do not expose VRAM or utilization through
    # nvidia-smi. Use i915 GT active/max frequency as a useful load proxy.
    intel_paths = list(Path("/sys/class/drm").glob("card*/device/gt_act_freq_mhz"))
    intel_paths += list(Path("/sys/class/drm").glob("card*/device/gt/gt*/gt_act_freq_mhz"))
    for active_path in intel_paths:
        try:
            active = float(active_path.read_text(encoding="utf-8").strip())
            maximum_path = active_path.with_name("gt_max_freq_mhz")
            maximum = float(maximum_path.read_text(encoding="utf-8").strip())
            if maximum > 0:
                gpu_name = next(
                    (part for part in active_path.parts if part.startswith("card") and part[4:].isdigit()), "card0"
                )
                return {
                    "gpus": [
                        {
                            "name": f"intel:{gpu_name}",
                            "usage_ratio": max(0.0, min(1.0, active / maximum)),
                            "memory_used": 0,
                            "memory_total": 0,
                        }
                    ]
                }
        except (OSError, ValueError):
            continue
    return None


def _refresh_ollama_model_resources(ollama_processes) -> None:
    """Split Ollama runner RSS/CPU by loaded model and expose Ollama VRAM."""
    global _observed_ollama_models
    for model in _observed_ollama_models:
        OLLAMA_MODEL_MEMORY.labels(model=model).set(0)
        OLLAMA_MODEL_VRAM.labels(model=model).set(0)
        OLLAMA_MODEL_CPU.labels(model=model).set(0)
        OLLAMA_MODEL_LOADED.labels(model=model).set(0)

    running_models = _running_ollama_models()
    active_names = set()
    runner_processes = [item for item in ollama_processes if item["is_runner"]]
    for item in running_models:
        model = str(item.get("name") or item.get("model") or "unknown")
        active_names.add(model)
        digest = _ollama_model_blob_digest(model)
        matches = [proc for proc in runner_processes if digest and digest in proc["command"]]
        if not matches and len(running_models) == 1:
            matches = runner_processes
        OLLAMA_MODEL_MEMORY.labels(model=model).set(sum(proc["memory"] for proc in matches))
        OLLAMA_MODEL_CPU.labels(model=model).set(sum(proc["cpu"] for proc in matches))
        OLLAMA_MODEL_VRAM.labels(model=model).set(max(0, int(item.get("size_vram") or 0)))
        OLLAMA_MODEL_LOADED.labels(model=model).set(1)
    _observed_ollama_models |= active_names


def refresh_resource_metrics() -> None:
    """Refresh gauges whose values come from the host/process at scrape time."""
    try:
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY.labels(state="total").set(memory.total)
        SYSTEM_MEMORY.labels(state="available").set(memory.available)
        SYSTEM_MEMORY.labels(state="used").set(memory.used)
        SYSTEM_MEMORY.labels(state="free").set(memory.free)
        SYSTEM_MEMORY.labels(state="percent").set(memory.percent)
        SYSTEM_CPU.set(psutil.cpu_percent(interval=None) / 100.0)
        gpu = _gpu_stats()
        if gpu:
            SYSTEM_GPU_AVAILABLE.set(1)
            active_gpus = {item["name"] for item in gpu["gpus"]}
            for item in gpu["gpus"]:
                name = item["name"]
                SYSTEM_GPU.labels(gpu=name).set(item["usage_ratio"])
                SYSTEM_GPU_MEMORY.labels(gpu=name, state="used").set(item["memory_used"])
                SYSTEM_GPU_MEMORY.labels(gpu=name, state="total").set(item["memory_total"])
                SYSTEM_GPU_MEMORY.labels(gpu=name, state="free").set(max(0, item["memory_total"] - item["memory_used"]))
            for name in getattr(refresh_resource_metrics, "_observed_gpus", set()) - active_gpus:
                SYSTEM_GPU.labels(gpu=name).set(0)
                for state in ("used", "total", "free"):
                    SYSTEM_GPU_MEMORY.labels(gpu=name, state=state).set(0)
            refresh_resource_metrics._observed_gpus = active_gpus
        else:
            SYSTEM_GPU_AVAILABLE.set(0)
            for name in getattr(refresh_resource_metrics, "_observed_gpus", set()):
                SYSTEM_GPU.labels(gpu=name).set(0)
                for state in ("used", "total", "free"):
                    SYSTEM_GPU_MEMORY.labels(gpu=name, state=state).set(0)
        info = _process.memory_info()
        ADA_PROCESS_MEMORY.set(info.rss)
        ADA_PROCESS_CPU.set(_process.cpu_percent(interval=None) / max(1.0, psutil.cpu_count() or 1) / 100.0)
        ADA_PROCESS_UPTIME.set(max(0.0, time.time() - _process_started))
        components = {"ada": False, "ollama": False, "telegram": False, "prometheus": False, "grafana": False}
        component_memory = {component: 0 for component in components}
        component_cpu = {component: 0.0 for component in components}
        ollama_processes = []
        for proc in psutil.process_iter(["name", "cmdline", "memory_info"]):
            try:
                command = " ".join(proc.info.get("cmdline") or []).lower()
                name = str(proc.info.get("name") or "").lower()
                if proc.pid == os.getpid() or (name.startswith("python") and "ada.interfaces.web.server" in command):
                    component = "ada"
                elif name == "ollama" or name == "llama-server":
                    component = "ollama"
                elif name.startswith("python") and ("telegram/bot.py" in command or "telegram.bot" in command):
                    component = "telegram"
                elif name.startswith("prometheus"):
                    component = "prometheus"
                elif name.startswith("grafana"):
                    component = "grafana"
                else:
                    continue
                memory_bytes = proc.info["memory_info"].rss if proc.info.get("memory_info") else 0
                cpu_ratio = proc.cpu_percent(interval=None) / max(1.0, psutil.cpu_count() or 1) / 100.0
                components[component] = True
                component_memory[component] += memory_bytes
                component_cpu[component] += cpu_ratio
                if component == "ollama":
                    ollama_processes.append(
                        {
                            "command": command,
                            "memory": memory_bytes,
                            "cpu": cpu_ratio,
                            "is_runner": name == "llama-server" or " runner " in f" {command} ",
                        }
                    )
            except (psutil.Error, OSError):
                continue
        for component, running in components.items():
            COMPONENT_RUNNING.labels(component=component).set(1 if running else 0)
            COMPONENT_MEMORY.labels(component=component).set(component_memory[component])
            COMPONENT_CPU.labels(component=component).set(component_cpu[component])
        _refresh_ollama_model_resources(ollama_processes)
    except (psutil.Error, OSError):
        pass


def operation_started(name: str) -> None:
    ADA_ACTIVE.labels(operation=name).inc()


def operation_finished(name: str) -> None:
    ADA_ACTIVE.labels(operation=name).dec()


def record_healthcheck_run(category: str, capability: str, status: str, duration: float) -> None:
    """Record an individual healthcheck / test case run in Prometheus."""
    try:
        cat = str(category or "general").lower()
        cap = str(capability or "unknown").lower()
        stat = str(status or "failed").lower()
        HEALTHCHECK_RUNS.labels(category=cat, capability=cap, status=stat).inc()
        sec = max(0.0, float(duration or 0.0))
        HEALTHCHECK_DURATION.labels(category=cat, capability=cap, status=stat).observe(sec)
    except Exception:
        pass


def record_healthcheck_judge(category: str, model: str, score: float) -> None:
    """Record AI judge score distribution in Prometheus."""
    try:
        cat = str(category or "general").lower()
        mod = str(model or "unknown").lower()
        val = max(0.0, min(1.0, float(score or 0.0)))
        HEALTHCHECK_JUDGE_SCORE.labels(category=cat, model=mod).observe(val)
    except Exception:
        pass


def record_healthcheck_batch(status: str) -> None:
    """Record batch lifecycle event."""
    try:
        stat = str(status or "completed").lower()
        HEALTHCHECK_BATCH_RUNS.labels(status=stat).inc()
    except Exception:
        pass


def set_active_healthcheck_batches(count: int) -> None:
    """Update active healthcheck batches gauge."""
    try:
        HEALTHCHECK_ACTIVE_BATCHES.set(max(0, int(count or 0)))
    except Exception:
        pass


def update_category_pass_rate(category: str, pass_rate: float) -> None:
    """Update category pass rate gauge."""
    try:
        cat = str(category or "general").lower()
        rate = max(0.0, min(1.0, float(pass_rate or 0.0)))
        HEALTHCHECK_PASS_RATE.labels(category=cat).set(rate)
    except Exception:
        pass


def record_router_decision(action: str, intent_type: str = "direct", status: str = "ok", confidence: float = 1.0) -> None:
    """Record intent router decision in Prometheus."""
    try:
        act = str(action or "ask").lower()
        itype = str(intent_type or "direct").lower()
        stat = str(status or "ok").lower()
        ROUTER_DECISIONS.labels(action=act, intent_type=itype, status=stat).inc()
        conf = max(0.0, min(1.0, float(confidence or 0.0)))
        ROUTER_CONFIDENCE.labels(action=act).observe(conf)
    except Exception:
        pass


def record_router_error(error_type: str) -> None:
    """Record a router error."""
    try:
        err = str(error_type or "unknown").lower()
        ROUTER_ERRORS.labels(error_type=err).inc()
    except Exception:
        pass


def record_router_fallback(trigger: str) -> None:
    """Record a router fallback invocation."""
    try:
        trig = str(trigger or "unknown").lower()
        ROUTER_FALLBACKS.labels(trigger=trig).inc()
    except Exception:
        pass


def record_llm_generation(model: str, tokens: int, duration: float, context_used: int = 0, context_max: int = DEFAULT_CONTEXT_WINDOW) -> None:
    """Record LLM generation throughput and context saturation."""
    try:
        mod = str(model or "unknown").lower()
        tok = max(0, int(tokens or 0))
        sec = max(0.001, float(duration or 0.0))
        speed = tok / sec
        LLM_GENERATION_SPEED.labels(model=mod).observe(speed)
        if context_max and context_max > 0:
            saturation = min(1.0, max(0.0, float(context_used or 0) / float(context_max)))
            LLM_CONTEXT_SATURATION.labels(model=mod).set(saturation)
    except Exception:
        pass


def record_llm_retry(model: str, reason: str) -> None:
    """Record LLM retry or model switch event."""
    try:
        mod = str(model or "unknown").lower()
        res = str(reason or "timeout").lower()
        LLM_RETRIES.labels(model=mod, reason=res).inc()
    except Exception:
        pass


def record_sqlite_op(table: str, operation: str, duration: float = 0.0) -> None:
    """Record SQLite database operation."""
    try:
        tbl = str(table or "unknown").lower()
        op = str(operation or "select").lower()
        SQLITE_QUERIES.labels(table=tbl, operation=op).inc()
        if duration > 0:
            SQLITE_QUERY_DURATION.labels(operation=op).observe(float(duration))
    except Exception:
        pass


def record_memory_refiner(status: str = "ok", extracted_facts: int = 0) -> None:
    """Record memory refiner cycle."""
    try:
        stat = str(status or "ok").lower()
        MEMORY_REFINER_RUNS.labels(status=stat).inc()
        if extracted_facts > 0:
            MEMORY_REFINER_FACTS.inc(int(extracted_facts))
    except Exception:
        pass


def record_telegram_event(direction: str, status: str = "ok", duration: float = None) -> None:
    """Record Telegram communication event."""
    try:
        direct = str(direction or "inbound").lower()
        stat = str(status or "ok").lower()
        TELEGRAM_MESSAGES.labels(direction=direct, status=stat).inc()
        if duration is not None and duration >= 0:
            TELEGRAM_LATENCY.observe(float(duration))
    except Exception:
        pass


def record_telegram_error(error_type: str) -> None:
    """Record Telegram polling or transport error."""
    try:
        err = str(error_type or "network").lower()
        TELEGRAM_POLLING_ERRORS.labels(error_type=err).inc()
    except Exception:
        pass


def record_system_error(component: str, error_class: str) -> None:
    """Record system error by component."""
    try:
        comp = str(component or "general").lower()
        err_cls = str(error_class or "exception").lower()
        SYSTEM_ERRORS.labels(component=comp, error_class=err_cls).inc()
    except Exception:
        pass


def exposition() -> bytes:
    """Return the OpenMetrics-compatible scrape payload."""
    refresh_resource_metrics()
    return generate_latest(REGISTRY)

