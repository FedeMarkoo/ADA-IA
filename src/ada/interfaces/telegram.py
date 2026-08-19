"""Telegram inbound adapter.

Telegram is deliberately kept at the edge of the application. It receives an
update, turns it into ADA's internal chat request, and forwards it to the same
localhost endpoint used by the web UI. No agent or capability logic belongs in
this module.
"""

import json
import logging
import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path


logger = logging.getLogger("ada.telegram")


class TelegramListener:
    def __init__(self, config=None, base_url="http://127.0.0.1:5005"):
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
    def _allowed_chat_ids(value):
        if isinstance(value, str):
            value = value.split(",")
        return {str(item).strip() for item in value if str(item).strip()}

    @property
    def enabled(self):
        configured = self.config.get("telegram", {}).get("enabled", False)
        return bool(self.token) and (configured or bool(os.environ.get("TELEGRAM_BOT_TOKEN")))

    def start(self):
        if not self.enabled:
            return None
        thread = threading.Thread(target=self.run, name="ada-telegram", daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.stop_event.set()

    def run(self):
        offset = None
        while not self.stop_event.is_set():
            try:
                updates = self._get_updates(offset)
                for update in updates:
                    offset = update.get("update_id", 0) + 1
                    self.handle_update(update)
            except Exception as exc:
                logger.exception("adapter error: %s", exc)
                self.stop_event.wait(max(self.poll_seconds, 3))

    def _api(self, method, payload=None):
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

    def _retry(self, function, operation, attempts=3):
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

    def _get_updates(self, offset):
        def call():
            query = {"timeout": 25, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                query["offset"] = offset
            url = f"{self.api_url}/getUpdates?{urllib.parse.urlencode(query)}"
            with urllib.request.urlopen(url, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not result.get("ok"):
                raise RuntimeError(result.get("description", "Telegram API error"))
            return result.get("result", [])

        return self._retry(call, "telegram_get_updates")

    def handle_update(self, update):
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

    def _invoke_internal_chat(self, text):
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

    def send_message(self, chat_id, text):
        text = str(text)
        for start in range(0, len(text), 4000):
            self._api("sendMessage", {"chat_id": chat_id, "text": text[start : start + 4000]})

    def _download_photo(self, photo):
        file_info = self._api("getFile", {"file_id": photo["file_id"]})
        file_path = file_info["file_path"]
        self.inbox.mkdir(parents=True, exist_ok=True)
        target = self.inbox / Path(file_path).name
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        with urllib.request.urlopen(url, timeout=60) as response:
            target.write_bytes(response.read())
        return str(target.resolve())
