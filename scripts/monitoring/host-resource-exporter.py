#!/usr/bin/env python3
"""Expose host process and memory metrics without exporting command lines."""

import re
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 9101
LISTEN_ADDRESS = "0.0.0.0"
COMPONENTS = ("ada", "litellm", "ollama", "telegram", "prometheus", "grafana")
RSS_PATTERN = re.compile(r"VmRSS:\s+(\d+)\s+kB")
MODEL_PATTERN = re.compile(r'"name"\s*:\s*"([^"]+)"')


def read_rss(process_path):
    try:
        match = RSS_PATTERN.search((process_path / "status").read_text())
        return int(match.group(1)) * 1024 if match else 0
    except (OSError, ValueError):
        return 0


def classify(name, command):
    if "ada.jar" in command or "ada-0.1.0-snapshot.jar" in command:
        return "ada"
    if name in ("ollama", "llama-server"):
        return "ollama"
    if "litellm" in command:
        return "litellm"
    if name.startswith("prometheus"):
        return "prometheus"
    if name.startswith("grafana"):
        return "grafana"
    if "telegram/bot" in command or "telegram.bot" in command:
        return "telegram"
    return None


def component_memory():
    result = dict.fromkeys(COMPONENTS, 0)
    for process_path in Path("/proc").glob("[0-9]*"):
        try:
            name = (process_path / "comm").read_text().strip().lower()
            command = (process_path / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore").lower()
            component = classify(name, command)
            if component:
                result[component] += read_rss(process_path)
        except OSError:
            continue
    return result


def system_memory():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        values[key] = int(value.strip().split()[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return total, available


def loaded_models():
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=1) as response:
            names = MODEL_PATTERN.findall(response.read().decode())
            return list(dict.fromkeys(names))
    except (OSError, ValueError):
        return []


def metrics():
    memory = component_memory()
    total, available = system_memory()
    lines = [
        "# HELP ada_host_component_memory_bytes Resident memory by host component.",
        "# TYPE ada_host_component_memory_bytes gauge",
    ]
    for component, value in memory.items():
        lines.append(f'ada_host_component_memory_bytes{{component="{component}"}} {value}')
    lines.extend(
        [
            "# HELP ada_host_system_memory_bytes Host memory in bytes.",
            "# TYPE ada_host_system_memory_bytes gauge",
            f'ada_host_system_memory_bytes{{state="total"}} {total}',
            f'ada_host_system_memory_bytes{{state="available"}} {available}',
            f'ada_host_system_memory_bytes{{state="used"}} {max(0, total - available)}',
        ]
    )
    models = loaded_models()
    model_memory = memory["ollama"] / len(models) if models else 0
    lines.extend(
        [
            "# HELP ada_host_ollama_model_memory_bytes Resident memory attributed to loaded Ollama models.",
            "# TYPE ada_host_ollama_model_memory_bytes gauge",
        ]
    )
    for model in models or ["unknown"]:
        lines.append(f'ada_host_ollama_model_memory_bytes{{model="{model}"}} {model_memory}')
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        body = metrics().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        return


if __name__ == "__main__":
    HTTPServer((LISTEN_ADDRESS, PORT), MetricsHandler).serve_forever()
