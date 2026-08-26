"""Prometheus instrumentation shared by the ADA process.

The registry is deliberately local to ADA so importing the web application in
tests or embedding it in another process does not mutate prometheus' global
registry. Prometheus scrapes this process directly; no local polling worker or
SQLite time-series database is needed.
"""

import json
import os
import time
import urllib.request
from pathlib import Path

import psutil
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, ProcessCollector, generate_latest


REGISTRY = CollectorRegistry(auto_describe=True)
ProcessCollector(registry=REGISTRY)

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
UP = Gauge("ada_up", "Whether the ADA web process is alive.", registry=REGISTRY)
UP.set(1)

_process = psutil.Process(os.getpid())
_process_started = time.time()
_observed_ollama_models = set()


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


def exposition() -> bytes:
    """Return the OpenMetrics-compatible scrape payload."""
    refresh_resource_metrics()
    return generate_latest(REGISTRY)
