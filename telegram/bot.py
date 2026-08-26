"""Standalone Telegram Bot Server and Adapter for ADA.

This runs as an independent daemon communicating with ADA's REST API over HTTP.
"""

import json
import logging
import os
import re
import sys
import threading
import urllib.parse
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
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
        self.request_timeout = float(
            telegram.get("request_timeout_seconds", self.config.get("chat_timeout_seconds", 900))
        )
        self.typing_enabled = bool(telegram.get("typing_indicator", True))
        self.typing_interval = max(1.0, float(telegram.get("typing_interval_seconds", 4.0)))
        self.allowed_chat_ids = self._allowed_chat_ids(
            os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "") or telegram.get("allowed_chat_ids", [])
        )
        self.inbox = Path(os.path.expanduser(str(telegram.get("inbox", "~/Desktop/ADA_Data/telegram_inbox"))))
        health_path = os.environ.get("ADA_TRIGGER_HEALTH_PATH") or telegram.get("health_path")
        self.health_path = Path(health_path).expanduser() if health_path else None
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

    def _write_health(self, status: str, error: Optional[str] = None, **details: Any) -> None:
        if not self.health_path:
            return
        payload = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_error": str(error or "")[:1000] or None,
            **details,
        }
        try:
            self.health_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.health_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.health_path)
        except OSError:
            logger.exception("telegram_health_write_failed")

    def run(self) -> None:
        offset = None
        logger.info("telegram_bot_started base_url=%s", self.base_url)
        self._write_health("starting")
        while not self.stop_event.is_set():
            try:
                updates = self._get_updates(offset)
                self._write_health("healthy", pending_updates=len(updates))
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
                conflict = "Telegram API 409" in str(exc)
                if conflict:
                    logger.error("telegram_listener_conflict error=%s", exc)
                else:
                    logger.exception("adapter error: %s", exc)
                self._write_health("degraded", error=exc)
                self.stop_event.wait(30 if conflict else max(self.poll_seconds, 3))

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
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8", "replace"))
                description = payload.get("description") or str(exc)
            except (ValueError, OSError):
                description = str(exc)
            raise RuntimeError(f"Telegram API {exc.code}: {description}") from exc
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
                if "Telegram API 409" in str(exc):
                    logger.error("%s conflict: %s", operation, exc)
                    break
                if attempt + 1 == attempts:
                    logger.exception("%s failed after %d attempts", operation, attempts)
                    break
                delay = min(30.0, max(1.0, self.poll_seconds) * (2**attempt))
                logger.warning("%s retry=%d delay=%.1fs", operation, attempt + 1, delay)
                self.stop_event.wait(delay)
        raise RuntimeError(f"{operation} failed: {last_error}") from last_error

    def _get_updates(self, offset: Optional[int]) -> list:
        def call():
            query: Dict[str, Any] = {"timeout": 25, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                query["offset"] = offset
            url = f"{self.api_url}/getUpdates?{urllib.parse.urlencode(query)}"
            try:
                with urllib.request.urlopen(url, timeout=35) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                try:
                    payload = json.loads(exc.read().decode("utf-8", "replace"))
                    description = payload.get("description") or str(exc)
                except (ValueError, OSError):
                    description = str(exc)
                raise RuntimeError(f"Telegram API {exc.code}: {description}") from exc
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

        typing_stop = threading.Event()
        status_msg_id = self.send_initial_status(chat_id, "⏳ *Procesando tu solicitud...*")
        typing_thread = self._start_typing_and_status(chat_id, typing_stop, status_msg_id)
        try:
            try:
                reply = self._invoke_internal_chat(text, chat_id=chat_id, sender=sender)
            except TypeError:
                reply = self._invoke_internal_chat(text)
        finally:
            typing_stop.set()
            if typing_thread:
                typing_thread.join(timeout=1.0)
        logger.info("chat_id=%s respuesta=%r", chat_id, str(reply)[:500])
        if status_msg_id:
            edited = self.edit_message(chat_id, status_msg_id, reply)
            if not edited:
                self.send_message(chat_id, reply)
        else:
            self.send_message(chat_id, reply)

    def _start_typing_and_status(self, chat_id: str, stop_event: threading.Event, status_msg_id: Optional[int] = None) -> Optional[threading.Thread]:
        """Keep Telegram typing alive and update the status message with real-time phase description."""
        if not self.typing_enabled or not chat_id:
            return None

        # Enviar acción de typing inmediata
        try:
            self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception as exc:
            logger.warning("telegram_typing_initial_failed chat_id=%s error=%s", chat_id, exc)

        def loop() -> None:
            last_status_text = ""
            while not stop_event.is_set() and not self.stop_event.is_set():
                stop_event.wait(self.typing_interval)
                if stop_event.is_set() or self.stop_event.is_set():
                    break
                try:
                    self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
                except Exception as exc:
                    logger.warning("telegram_typing_indicator_failed chat_id=%s error=%s", chat_id, exc)

                # Si tenemos un mensaje de estado, consultar la fase actual del núcleo y actualizar el mensaje
                if status_msg_id:
                    try:
                        req = urllib.request.Request(f"{self.base_url}/api/core/state", method="GET")
                        with urllib.request.urlopen(req, timeout=4) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            act = data.get("activity") or {}
                            if act.get("status") == "working":
                                label = act.get("label") or "Procesando"
                                detail = act.get("detail") or ""
                                text_parts = [f"⚙️ {label}"]
                                if detail and detail != label:
                                    text_parts.append(f"({detail})")
                                status_display = " ".join(text_parts)
                                if status_display != last_status_text:
                                    last_status_text = status_display
                                    self.edit_message(chat_id, status_msg_id, f"{status_display}...")
                    except Exception:
                        pass

        thread = threading.Thread(target=loop, name=f"ada-telegram-typing-{chat_id}", daemon=True)
        thread.start()
        return thread

    def send_initial_status(self, chat_id: str, text: str) -> Optional[int]:
        """Send an initial placeholder message that will be edited as processing continues."""
        try:
            res = self._api("sendMessage", {"chat_id": chat_id, "text": text})
            if res and isinstance(res, dict):
                return res.get("message_id")
        except Exception as exc:
            logger.warning("telegram_initial_status_send_failed chat_id=%s error=%s", chat_id, exc)
        return None

    def edit_message(self, chat_id: str, message_id: int, text: str) -> bool:
        """Edit an existing message with updated text or final response."""
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", str(text), flags=re.DOTALL)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        if len(text) > 4000:
            text = text[:3990] + "..."
        try:
            self._api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text})
            return True
        except Exception as exc:
            logger.warning("telegram_edit_message_failed chat_id=%s message_id=%s error=%s", chat_id, message_id, exc)
            return False

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
        # Allow the local agent budget to finish before the Telegram adapter
        # gives up and reports a misleading connection failure.
        with urllib.request.urlopen(request, timeout=max(60, self.request_timeout + 60)) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("reply") or result.get("error") or "ADA no devolvió una respuesta."

    def send_message(self, chat_id: str, text: str) -> Optional[int]:
        # Web chat replies may contain Markdown, while Telegram is sent as
        # plain text here. Remove presentation markers so users do not see
        # literal `**bold**` or backticks in the conversation.
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", str(text), flags=re.DOTALL)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        last_message_id = None
        for start in range(0, len(text), 4000):
            result = self._api("sendMessage", {"chat_id": chat_id, "text": text[start : start + 4000]})
            if isinstance(result, dict):
                last_message_id = result.get("message_id")
        return last_message_id

    def edit_message_text(self, chat_id: str, message_id: int, text: str) -> None:
        """Edit an existing bot message instead of sending a second one."""
        self._api("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": str(text),
        })

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
    cfg_path = PROJECT_ROOT / "ada" / "config.json"
    if not cfg_path.is_file():
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
