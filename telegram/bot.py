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
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("ada.telegram")


def resolve_telegram_token(config: Optional[Dict[str, Any]] = None) -> str:
    if config:
        tg_cfg = config.get("telegram", {}) if isinstance(config.get("telegram"), dict) else {}
        if "token" in tg_cfg or "bot_token" in tg_cfg:
            return str(tg_cfg.get("token") or tg_cfg.get("bot_token") or "").strip()
        if "telegram_token" in config:
            return str(config.get("telegram_token") or "").strip()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token

    try:
        from utils.credentials import SecureVault
        token = SecureVault().get("telegram_bot_token") or SecureVault().get("telegram_token")
        if token:
            return str(token).strip()
    except Exception:
        pass
    cfg_file = PROJECT_ROOT / "ada" / "config.json"
    if not cfg_file.is_file():
        cfg_file = PROJECT_ROOT / "config.json"
    if cfg_file.is_file():
        try:
            c = json.loads(cfg_file.read_text(encoding="utf-8"))
            tg_c = c.get("telegram", {}) if isinstance(c.get("telegram"), dict) else {}
            token = str(tg_c.get("token") or tg_c.get("bot_token") or c.get("telegram_token") or "").strip()
            if token:
                return token
        except Exception:
            pass
    for env_path in [PROJECT_ROOT / ".env", Path.home() / ".env", Path.home() / ".config" / "ada" / ".env"]:
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
            except Exception:
                pass
    return ""


class TelegramListener:
    """Independent Telegram polling bot daemon forwarding to ADA REST endpoints."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, base_url: str = "http://127.0.0.1:5005"):
        self.config = config or {}
        telegram = self.config.get("telegram", {})
        self.token = resolve_telegram_token(self.config)
        self.base_url = os.environ.get("ADA_INTERNAL_URL", base_url).rstrip("/")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.poll_seconds = float(telegram.get("poll_seconds", 2))
        self.allowed_chat_ids = self._allowed_chat_ids(
            os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "") or telegram.get("allowed_chat_ids", [])
        )
        self.inbox = Path(os.path.expanduser(str(telegram.get("inbox", "~/Desktop/ADA_Data/telegram_inbox"))))
        self.stop_event = threading.Event()
        self._processed_update_ids: Set[int] = set()
        self._processed_update_order = deque(maxlen=2048)

    @staticmethod
    def _allowed_chat_ids(value: Any) -> Set[str]:
        if isinstance(value, str):
            value = value.split(",")
        return {str(item).strip() for item in value if str(item).strip()}

    @property
    def enabled(self) -> bool:
        return bool(self.token)

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
                    update_id = update.get("update_id")
                    if update_id is not None:
                        update_id = int(update_id)
                        if update_id in self._processed_update_ids:
                            logger.warning("telegram_update_duplicate_skipped update_id=%s", update_id)
                            offset = max(offset or 0, update_id + 1)
                            continue
                    offset = (update_id + 1) if update_id is not None else offset
                    self.handle_update(update)
            except Exception as exc:
                logger.exception("adapter error: %s", exc)
                self.stop_event.wait(max(self.poll_seconds, 3))

    def _remember_update(self, update_id: int) -> None:
        if update_id in self._processed_update_ids:
            return
        if len(self._processed_update_order) == self._processed_update_order.maxlen:
            oldest = self._processed_update_order.popleft()
            self._processed_update_ids.discard(oldest)
        self._processed_update_order.append(update_id)
        self._processed_update_ids.add(update_id)

    def _api(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        """Call Telegram without retrying side-effecting methods such as sendMessage."""
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
        update_id = update.get("update_id")
        if update_id is not None:
            update_id = int(update_id)
            if update_id in self._processed_update_ids:
                logger.warning("telegram_update_duplicate_skipped update_id=%s", update_id)
                return
            self._remember_update(update_id)

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = str(chat.get("id", ""))
        username = sender.get("username") or ""
        first_name = sender.get("first_name") or sender.get("last_name") or username or f"User_{chat_id}"

        if chat_id:
            logger.info("chat_id=%s from=%s (@%s) update_id=%s", chat_id, first_name, username, update_id)
        if not chat_id or (self.allowed_chat_ids and chat_id not in self.allowed_chat_ids):
            return

        text = (message.get("text") or message.get("caption") or "").strip()
        photos = message.get("photo") or []
        logger.info("chat_id=%s mensaje_recibido=%r", chat_id, text[:100])
        command = text.lower().split()[0] if text.startswith("/") else ""
        if command in {"/start", "/help"}:
            self.send_message(
                chat_id,
                f"¡Hola {first_name}! ADA está lista. Enviame una consulta, una foto o /status. Comandos: /help, /status, /cancel.",
            )
            return
        if command == "/cancel":
            self.send_message(chat_id, self._invoke_internal_chat("cancelar", chat_id=chat_id, sender=sender))
            return
        if command == "/status":
            self.send_message(chat_id, self._status_summary())
            return
        if photos:
            path = self._download_photo(photos[-1])
            text = f"{text}\nAnalizá la imagen descargada: {path}".strip()
        if not text:
            self.send_message(chat_id, "Puedo procesar texto y fotos. Enviame un mensaje o una imagen con una consulta.")
            return

        try:
            reply = self._invoke_internal_chat(text, chat_id=chat_id, sender=sender)
        except TypeError:
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

    def _invoke_internal_chat(self, text: str, chat_id: str = "", sender: Optional[Dict[str, Any]] = None) -> str:
        sender = sender or {}
        username = sender.get("username", "")
        first_name = sender.get("first_name", "") or sender.get("last_name", "") or username or f"User_{chat_id}"
        conversation_id = f"telegram_{chat_id}" if chat_id else "telegram_default"
        payload = json.dumps({
            "message": text,
            "lang": "es",
            "source": "telegram",
            "session_id": conversation_id,
            "conversation_id": conversation_id,
            "chat_id": str(chat_id),
            "username": f"@{username}" if username and not username.startswith("@") else username,
            "first_name": first_name,
            "user_id": str(sender.get("id", chat_id)),
            "metadata": {
                "chat_id": str(chat_id),
                "username": f"@{username}" if username and not username.startswith("@") else username,
                "first_name": first_name,
                "channel": "telegram",
            }
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "X-ADA-Source": "telegram"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("reply") or result.get("error") or "ADA no devolvió una respuesta."

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
        print("⚠️ Telegram bot no configurado. Configuralo en la Bóveda de Credenciales (vault.db) desde el Gestor Web.")
        sys.exit(1)

    print("🚀 Servidor Telegram Bot iniciando...")
    bot.run()


if __name__ == "__main__":
    main()
