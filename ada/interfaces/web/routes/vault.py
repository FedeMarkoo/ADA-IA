"""Secure Vault management and credentials routes for ADA web interface."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections import deque
from flask import Blueprint, jsonify, request

from ada.infrastructure.credentials import SecureVault
from ada.interfaces.web.state import resolve_telegram_token

logger = logging.getLogger("ada.web.vault")
vault_bp = Blueprint("vault", __name__)

# Basic sliding-window rate limiter for vault mutations (max 30 ops per minute)
_mutation_timestamps: deque = deque(maxlen=100)


def _check_rate_limit(max_per_minute: int = 30) -> bool:
    now = time.time()
    while _mutation_timestamps and _mutation_timestamps[0] < now - 60:
        _mutation_timestamps.popleft()
    if len(_mutation_timestamps) >= max_per_minute:
        return False
    _mutation_timestamps.append(now)
    return True


@vault_bp.route("/api/vault/keys")
def vault_keys_api():
    try:
        vault = SecureVault()
        keys = vault.list_keys()
        return jsonify({"ok": True, "keys": keys, "vault_path": str(vault.path)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@vault_bp.route("/api/vault/set", methods=["POST"])
def vault_set_api():
    if not _check_rate_limit(30):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "rate_limit_exceeded",
                    "message": "Demasiadas operaciones en poco tiempo. Reintentá en un minuto.",
                }
            ),
            429,
        )

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    value = body.get("value")
    meta = body.get("meta") or {}
    if not name:
        return jsonify({"ok": False, "error": "El nombre del secreto es requerido"}), 400
    if value is None or value == "":
        return jsonify({"ok": False, "error": "El valor del secreto no puede estar vacío"}), 400
    try:
        vault = SecureVault()
        vault.set(name, value, meta=meta)
        return jsonify({"ok": True, "message": f"Secreto '{name}' cifrado con éxito en vault.db"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@vault_bp.route("/api/vault/<name>", methods=["DELETE"])
def vault_delete_api(name):
    if not _check_rate_limit(30):
        return (
            jsonify({"ok": False, "error": "rate_limit_exceeded", "message": "Demasiadas operaciones en poco tiempo."}),
            429,
        )

    try:
        vault = SecureVault()
        deleted = vault.delete(name)
        if deleted:
            return jsonify({"ok": True, "message": f"Secreto '{name}' eliminado de la bóveda"})
        return jsonify({"ok": False, "error": f"Secreto '{name}' no encontrado"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@vault_bp.route("/api/telegram/test", methods=["POST"])
def telegram_test_api():
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip() or resolve_telegram_token()
    if not token:
        return jsonify({"ok": False, "error": "TELEGRAM_BOT_TOKEN no configurado"}), 400
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "ADA-Hub"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return jsonify(
                    {
                        "ok": True,
                        "bot": data.get("result"),
                        "token_masked": token[:6] + "..." + token[-4:] if len(token) > 10 else "***",
                    }
                )
            return jsonify({"ok": False, "error": data.get("description", "Error de Telegram")})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})
