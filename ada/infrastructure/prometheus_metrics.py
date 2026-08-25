"""Prometheus instrumentation shared by the ADA process.

The registry is deliberately local to ADA so importing the web application in
tests or embedding it in another process does not mutate prometheus' global
registry. Prometheus scrapes this process directly; no local polling worker or
SQLite time-series database is needed.
"""

import os
import time

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
UP = Gauge("ada_up", "Whether the ADA web process is alive.", registry=REGISTRY)
UP.set(1)

_process = psutil.Process(os.getpid())
_process_started = time.time()


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
