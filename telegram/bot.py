"""Standalone Telegram Bot Server and Adapter for ADA.

This runs as an independent daemon communicating with ADA's REST API over HTTP.
"""

import json
import logging
import os
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("ada.telegram")


class TelegramListener:
    """Independent Telegram polling bot daemon forwarding to ADA REST endpoints."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, base_url: str = "http://127.0.0.1:5005"):
        self.config = config or {}
        telegram = self.config.get("telegram", {})
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.base_url = os.environ.get("ADA_INTERNAL_URL", base_url).rstrip("/")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.poll_seconds = float(telegram.get("poll_seconds", 2))
        self.allowed_chat_ids = self._allowed_chat_ids(
            os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "") or telegram.get("allowed_chat_ids", [])
        )
        self.inbox = Path(telegram.get("inbox", "telegram_inbox"))
        self.stop_event = threading.Event()

    @staticmethod
    def _allowed_chat_ids(value: Any) -> Set[str]:
        if isinstance(value, str):
            value = value.split(",")
        return {str(item).strip() for item in value if str(item).strip()}

    @property
    def enabled(self) -> bool:
        configured = self.config.get("telegram", {}).get("enabled", False)
        return bool(self.token) and (configured or bool(os.environ.get("TELEGRAM_BOT_TOKEN")))

    def start(self) -> Optional[threading.Thread]:
        if not self.enabled:
            return None
        thread = threading.Thread(target=self.run, name="ada-telegram", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        offset = None
        logger.info("telegram_bot_started base_url=%s", self.base_url)
        while not self.stop_event.is_set():
            try:
                updates = self._get_updates(offset)
                for update in updates:
                    offset = update.get("update_id", 0) + 1
                    self.handle_update(update)
            except Exception as exc:
                logger.exception("adapter error: %s", exc)
                self.stop_event.wait(max(self.poll_seconds, 3))

    def _api(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        def call():
            data = None
            url = f"{self.api_url}/{method}"
            if payload:
                data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST" if data else "GET",
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not result.get("ok"):
                raise RuntimeError(result.get("description", "Telegram API error"))
            return result.get("result")

        return self._retry(call, f"telegram_api method={method}")

    def _retry(self, function, operation: str, attempts: int = 3) -> Any:
        last_error = None
        for attempt in range(attempts):
            try:
                return function()
            except (OSError, ValueError, RuntimeError) as exc:
                last_error = exc
                if attempt + 1 == attempts:
                    logger.exception("%s failed after %d attempts", operation, attempts)
                    break
                delay = min(30.0, max(1.0, self.poll_seconds) * (2**attempt))
                logger.warning("%s retry=%d delay=%.1fs", operation, attempt + 1, delay)
                self.stop_event.wait(delay)
        raise RuntimeError(f"{operation} failed") from last_error

    def _get_updates(self, offset: Optional[int]) -> list:
        def call():
            query: Dict[str, Any] = {"timeout": 25, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                query["offset"] = offset
            url = f"{self.api_url}/getUpdates?{urllib.parse.urlencode(query)}"
            with urllib.request.urlopen(url, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not result.get("ok"):
                raise RuntimeError(result.get("description", "Telegram API error"))
            return result.get("result", [])

        return self._retry(call, "telegram_get_updates")

    def handle_update(self, update: Dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        if chat_id:
            logger.info("chat_id=%s", chat_id)
        if not chat_id or (self.allowed_chat_ids and chat_id not in self.allowed_chat_ids):
            return

        text = (message.get("text") or message.get("caption") or "").strip()
        photos = message.get("photo") or []
        logger.info("chat_id=%s mensaje_recibido", chat_id)
        command = text.lower().split()[0] if text.startswith("/") else ""
        if command in {"/start", "/help"}:
            self.send_message(
                chat_id,
                "ADA lista. Enviame una consulta, una foto o /status. Comandos: /help, /status, /cancel.",
            )
            return
        if command == "/cancel":
            self.send_message(chat_id, self._invoke_internal_chat("cancelar"))
            return
        if command == "/status":
            self.send_message(chat_id, self._status_summary())
            return
        if photos:
            path = self._download_photo(photos[-1])
            text = f"{text}\nAnalizá la imagen descargada: {path}".strip()
        if not text:
            self.send_message(
                chat_id, "Puedo procesar texto y fotos. Enviame un mensaje o una imagen con una consulta."
            )
            return

        reply = self._invoke_internal_chat(text)
        logger.info("chat_id=%s respuesta=%r", chat_id, str(reply)[:500])
        self.send_message(chat_id, reply)

    def _status_summary(self) -> str:
        def call():
            request = urllib.request.Request(f"{self.base_url}/api/status", method="GET")
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
            engines = ", ".join(name for name, enabled in data.get("engines", {}).items() if enabled) or "ninguno"
            return f"ADA online. Motores disponibles: {engines}. Agentes: {len(data.get('agents', []))}."

        return self._retry(call, "telegram_status")

    def _invoke_internal_chat(self, text: str) -> str:
        def call():
            payload = json.dumps({"message": text, "lang": "es", "source": "telegram"}).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
            return result.get("reply") or result.get("error") or "ADA no devolvió una respuesta."

        return self._retry(call, "telegram_internal_chat")

    def send_message(self, chat_id: str, text: str) -> None:
        text = str(text)
        for start in range(0, len(text), 4000):
            self._api("sendMessage", {"chat_id": chat_id, "text": text[start : start + 4000]})

    def _download_photo(self, photo: Dict[str, Any]) -> str:
        file_info = self._api("getFile", {"file_id": photo["file_id"]})
        file_path = file_info["file_path"]
        self.inbox.mkdir(parents=True, exist_ok=True)
        target = self.inbox / Path(file_path).name
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        with urllib.request.urlopen(url, timeout=60) as response:
            target.write_bytes(response.read())
        return str(target.resolve())


# Alias for clarity
TelegramBot = TelegramListener


def main():
    """CLI Entry point to run Telegram Bot independently."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    cfg_path = PROJECT_ROOT / "config.json"
    cfg = {}
    if cfg_path.is_file():
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    bot = TelegramListener(cfg)
    if not bot.enabled:
        print("⚠️ Telegram bot no configurado. Configurá TELEGRAM_BOT_TOKEN en variables de entorno o config.json.")
        sys.exit(1)

    print("🚀 Servidor Telegram Bot iniciando...")
    bot.run()


if __name__ == "__main__":
    main()
