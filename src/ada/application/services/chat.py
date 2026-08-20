"""Session-aware application service for chat channels."""

from dataclasses import dataclass, field
import threading

from ada.application.services.web_chat import WebChatService


@dataclass
class SessionState:
    messages: list = field(default_factory=list)
    pending_action: object = None
    lock: object = field(default_factory=threading.RLock)

    @property
    def conversation(self):
        return self.messages


class ChatService:
    def __init__(self, agent):
        self.agent = agent
        self.web_chat = WebChatService(agent)
        self._sessions = {}
        self._lock = threading.RLock()

    def session(self, session_id="main"):
        with self._lock:
            return self._sessions.setdefault(str(session_id), SessionState())

    def _remember(self, state, role, text):
        state.messages.append({"role": role, "text": str(text)})
        state.messages[:] = state.messages[-1000:]

    def handle(self, message, session_id="main", lang=None, confirm=None):
        state = self.session(session_id)
        with state.lock:
            if confirm is False and state.pending_action:
                state.pending_action = None
                result, _status = self.web_chat.handle("cancelar", state, lang)
                return result
            result, _status = self.web_chat.handle(message, state, lang)
            if confirm is not None and state.pending_action and confirm:
                result, _status = self.web_chat.handle("confirmo", state, lang)
            return result

    def history(self, session_id="main"):
        return list(self.session(session_id).messages)

    def clear(self, session_id="main"):
        with self._lock:
            self._sessions.pop(str(session_id), None)
