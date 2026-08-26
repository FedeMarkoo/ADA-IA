"""Read-only public transport status capability.

The first adapter targets the Buenos Aires transport API. Credentials and the
endpoint are configuration-only; ADA never scrapes a private app session.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict

CAPABILITY_SPEC = {
    "name": "transport_status",
    "description": "Consulta el estado y alertas de una línea de transporte, inicialmente Sarmiento.",
    "risk_level": "low",
    "permissions": ["network.read"],
    "requires_confirmation": False,
    "version": "1.0",
    "argument_schema": {
        "type": "object",
        "properties": {
            "line": {"type": "string", "enum": ["sarmiento"]},
            "station": {"type": "string"},
            "direction": {"type": "string"},
            "config": {"type": "object"},
        },
        "required": ["line"],
        "additionalProperties": False,
    },
}

# Kept as a compatibility import for existing callers/tests. The public
# registry skips this module because transport_status is now exposed by the
# transport MCP as transport.get_status.
MCP_ONLY = True


def _config(args: Dict[str, Any]) -> Dict[str, Any]:
    config = args.get("config") if isinstance(args.get("config"), dict) else {}
    return config.get("transport") if isinstance(config.get("transport"), dict) else config


def _request_json(url: str, token: str, timeout: float) -> Any:
    headers = {"Accept": "application/json", "User-Agent": "ADA-IA/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["x-api-key"] = token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize_alerts(payload: Any) -> list[Dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("alerts") or payload.get("items") or payload.get("data") or []
    else:
        items = payload
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get("header_text") or item.get("description") or item.get("title") or item.get("summary")
        if isinstance(text, dict):
            text = next(iter(text.values()), "")
        result.append(
            {
                "title": str(item.get("title") or item.get("header") or "Alerta de servicio"),
                "description": str(text or ""),
                "active": item.get("active", True),
                "source": item.get("source") or "Buenos Aires Transporte API",
            }
        )
    return result


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    args = args or {}
    line = str(args.get("line") or "sarmiento").strip().lower()
    if line != "sarmiento":
        return {"ok": False, "error": "line_not_supported", "line": line}
    config = _config(args)
    base_url = str(
        config.get("api_base_url")
        or os.environ.get("ADA_TRANSPORT_API_BASE_URL", "https://api-transporte.buenosaires.gob.ar")
    ).rstrip("/")
    token = str(config.get("api_token") or os.environ.get("ADA_TRANSPORT_API_TOKEN", "")).strip()
    timeout = max(1.0, float(config.get("timeout_seconds", 8)))
    observed_at = datetime.now(timezone.utc).isoformat()
    if not token:
        return {
            "ok": False,
            "status": "unknown",
            "line": line,
            "observed_at": observed_at,
            "source": "Buenos Aires Transporte API",
            "error": "transport_api_token_missing",
            "message": "No hay token configurado para consultar datos en vivo; no se puede confirmar el estado actual.",
        }
    endpoint = str(config.get("service_alerts_path", "/trenes/serviceAlerts"))
    params = {"route_id": str(config.get("sarmiento_route_id", "Sarmiento"))}
    url = f"{base_url}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(params)}"
    try:
        payload = _request_json(url, token, timeout)
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {
            "ok": False,
            "status": "unknown",
            "line": line,
            "observed_at": observed_at,
            "source": "Buenos Aires Transporte API",
            "error": "transport_feed_unavailable",
            "detail": str(exc),
        }
    alerts = _normalize_alerts(payload)
    return {
        "ok": True,
        "status": "realtime" if isinstance(payload, dict) else "unknown",
        "line": line,
        "station": args.get("station"),
        "direction": args.get("direction"),
        "observed_at": observed_at,
        "source": "Buenos Aires Transporte API",
        "alerts": alerts,
        "message": "No se detectaron alertas activas." if not alerts else "Hay alertas de servicio para revisar.",
    }
