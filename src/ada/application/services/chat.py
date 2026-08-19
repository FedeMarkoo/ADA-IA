"""Session-aware application service for chat channels."""
from dataclasses import dataclass, field
import threading


@dataclass
class SessionState:
    messages: list = field(default_factory=list)
    pending_action: object = None


class ChatService:
    def __init__(self, agent):
        self.agent = agent
        self._sessions = {}
        self._lock = threading.RLock()

    def session(self, session_id='main'):
        with self._lock:
            return self._sessions.setdefault(str(session_id), SessionState())

    def _remember(self, state, role, text):
        state.messages.append({'role': role, 'text': str(text)})
        state.messages[:] = state.messages[-1000:]

    def handle(self, message, session_id='main', lang=None, confirm=None):
        text = str(message or '').strip()
        if not text:
            return {'error': 'empty_message'}
        state = self.session(session_id)
        if lang:
            self.agent.lang = lang
        self._remember(state, 'user', text)
        parsed = self.agent.parse_prompt(text)
        action = parsed.get('action')
        payload = {key: value for key, value in parsed.items() if key not in {'action', 'complexity'}}
        task = {'type': action if action not in {'ask', 'suggest'} else None,
                'payload': payload, 'prompt': text,
                'complexity': parsed.get('complexity', 3), 'confirm': confirm}
        result = self.agent.decide_and_run(task)
        output = result.get('result', result) if isinstance(result, dict) else result
        reply = output.get('text') if isinstance(output, dict) else str(output)
        if isinstance(output, dict) and not reply:
            reply = str(output)
        self._remember(state, 'assistant', reply)
        return {'reply': reply, 'model': result.get('model') if isinstance(result, dict) else None,
                'action': action, 'result': output}

    def history(self, session_id='main'):
        return list(self.session(session_id).messages)

    def clear(self, session_id='main'):
        with self._lock:
            self._sessions.pop(str(session_id), None)
