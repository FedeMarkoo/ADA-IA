"""Monitoring management module for Prometheus and Grafana."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("ada.monitoring")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMETHEUS_BIN = PROJECT_ROOT / ".monitoring" / "bin" / "prometheus"
PROMETHEUS_CONFIG = PROJECT_ROOT / ".monitoring" / "prometheus-local.yml"
PROMETHEUS_DATA = PROJECT_ROOT / ".monitoring" / "data"
PROMETHEUS_LOGS = PROJECT_ROOT / ".monitoring" / "logs" / "prometheus.log"

PROMETHEUS_URL = os.environ.get("ADA_PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
GRAFANA_URL = os.environ.get("ADA_GRAFANA_URL", "http://127.0.0.1:3000").rstrip("/")

_prom_proc: Optional[subprocess.Popen] = None
_prom_lock = threading.RLock()


def _http_check(url: str, timeout: float = 1.5) -> Dict[str, Any]:
    """Helper to perform HTTP health check."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ADA-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
                return {"online": True, "status_code": resp.status, "data": parsed}
            except Exception:
                return {"online": True, "status_code": resp.status, "raw": body[:200]}
    except urllib.error.HTTPError as e:
        return {"online": True, "status_code": e.code, "error": str(e)}
    except Exception as e:
        return {"online": False, "error": str(e)}


def _find_prometheus_pid() -> Optional[int]:
    """Find running prometheus process PID if any."""
    global _prom_proc
    with _prom_lock:
        if _prom_proc is not None and _prom_proc.poll() is None:
            return _prom_proc.pid
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "prometheus" in cmd and ("--config.file" in cmd or "prometheus-local.yml" in cmd):
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return None


def _find_grafana_pid() -> Optional[int]:
    """Find running grafana server process PID if any."""
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "grafana" in cmd and ("server" in cmd or "/usr/sbin/grafana" in cmd or "/usr/share/grafana" in cmd):
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return None


# ==============================================================================
# Status Checks
# ==============================================================================

def get_prometheus_status() -> Dict[str, Any]:
    """Get Prometheus health, running status, and process PID."""
    pid = _find_prometheus_pid()
    health = _http_check(f"{PROMETHEUS_URL}/-/healthy")
    running = health["online"] or pid is not None
    return {
        "name": "Prometheus",
        "url": PROMETHEUS_URL,
        "running": running,
        "online": health["online"],
        "pid": pid,
        "health": health,
        "binary_present": PROMETHEUS_BIN.is_file(),
        "config_present": PROMETHEUS_CONFIG.is_file(),
    }


def get_grafana_status() -> Dict[str, Any]:
    """Get Grafana health, version, running status, and process PID."""
    pid = _find_grafana_pid()
    health = _http_check(f"{GRAFANA_URL}/api/health")
    running = health["online"] or pid is not None
    return {
        "name": "Grafana",
        "url": GRAFANA_URL,
        "running": running,
        "online": health["online"],
        "pid": pid,
        "health": health,
    }


def get_monitoring_status() -> Dict[str, Any]:
    """Get aggregate status of the monitoring telemetry subsystem."""
    prom = get_prometheus_status()
    graf = get_grafana_status()
    return {
        "ok": prom["online"] and graf["online"],
        "prometheus": prom,
        "grafana": graf,
        "all_running": prom["running"] and graf["running"],
    }


# ==============================================================================
# Prometheus Control
# ==============================================================================

def start_prometheus() -> Dict[str, Any]:
    """Start local Prometheus instance scraping ADA metrics."""
    global _prom_proc
    status = get_prometheus_status()
    if status["online"]:
        return {"ok": True, "message": "Prometheus ya está en ejecución", "status": status}

    if not PROMETHEUS_BIN.is_file():
        return {"ok": False, "error": f"Binario de Prometheus no encontrado en {PROMETHEUS_BIN}"}

    PROMETHEUS_DATA.mkdir(parents=True, exist_ok=True)
    PROMETHEUS_LOGS.parent.mkdir(parents=True, exist_ok=True)

    with _prom_lock:
        try:
            log_file = open(PROMETHEUS_LOGS, "a", encoding="utf-8")
            _prom_proc = subprocess.Popen(
                [
                    str(PROMETHEUS_BIN),
                    f"--config.file={PROMETHEUS_CONFIG}",
                    f"--storage.tsdb.path={PROMETHEUS_DATA}",
                    "--web.listen-address=127.0.0.1:9090",
                    "--storage.tsdb.retention.time=15d",
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            time.sleep(1.0)
            new_status = get_prometheus_status()
            return {
                "ok": new_status["online"] or new_status["running"],
                "message": "Prometheus iniciado exitosamente",
                "status": new_status,
            }
        except Exception as exc:
            logger.exception("prometheus_start_failed")
            return {"ok": False, "error": f"Error al iniciar Prometheus: {exc}"}


def stop_prometheus() -> Dict[str, Any]:
    """Stop Prometheus process."""
    global _prom_proc
    pid = _find_prometheus_pid()
    if not pid:
        return {"ok": True, "message": "Prometheus no está en ejecución", "status": get_prometheus_status()}

    try:
        import psutil
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()
    except Exception:
        try:
            os.kill(pid, 15)
        except Exception:
            pass

    with _prom_lock:
        _prom_proc = None

    time.sleep(0.5)
    return {"ok": True, "message": "Prometheus detenido", "status": get_prometheus_status()}


def restart_prometheus() -> Dict[str, Any]:
    """Restart Prometheus process."""
    stop_prometheus()
    time.sleep(0.5)
    return start_prometheus()


# ==============================================================================
# Grafana Control
# ==============================================================================

def start_grafana() -> Dict[str, Any]:
    """Start Grafana system service or process."""
    status = get_grafana_status()
    if status["online"]:
        return {"ok": True, "message": "Grafana ya está en ejecución", "status": status}

    try:
        res = subprocess.run(["systemctl", "start", "grafana-server"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            time.sleep(1.5)
            return {"ok": True, "message": "Servicio grafana-server iniciado", "status": get_grafana_status()}
    except Exception:
        pass

    try:
        # Fallback to direct binary if available
        if Path("/usr/sbin/grafana-server").exists():
            subprocess.Popen(["/usr/sbin/grafana-server", "--config=/etc/grafana/grafana.ini"], start_new_session=True)
            time.sleep(1.5)
            return {"ok": True, "message": "Grafana iniciado", "status": get_grafana_status()}
    except Exception as exc:
        return {"ok": False, "error": f"Error al iniciar Grafana: {exc}"}

    return {"ok": False, "error": "No se pudo iniciar grafana-server (verificar permisos systemctl)"}


def stop_grafana() -> Dict[str, Any]:
    """Stop Grafana system service or process."""
    try:
        res = subprocess.run(["systemctl", "stop", "grafana-server"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            time.sleep(0.5)
            return {"ok": True, "message": "Servicio grafana-server detenido", "status": get_grafana_status()}
    except Exception:
        pass
    pid = _find_grafana_pid()
    if pid:
        try:
            os.kill(pid, 15)
            time.sleep(0.5)
        except Exception:
            pass
    return {"ok": True, "message": "Grafana detenido", "status": get_grafana_status()}


def restart_grafana() -> Dict[str, Any]:
    """Restart Grafana service."""
    try:
        res = subprocess.run(["systemctl", "restart", "grafana-server"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            time.sleep(1.5)
            return {"ok": True, "message": "Servicio grafana-server reiniciado", "status": get_grafana_status()}
    except Exception:
        pass
    stop_grafana()
    time.sleep(0.5)
    return start_grafana()


def start_monitoring_all() -> Dict[str, Any]:
    """Ensure both Prometheus and Grafana are running."""
    prom_res = start_prometheus()
    graf_res = start_grafana()
    return {
        "ok": prom_res.get("ok", False) and graf_res.get("ok", False),
        "prometheus": prom_res,
        "grafana": graf_res,
        "status": get_monitoring_status(),
    }
