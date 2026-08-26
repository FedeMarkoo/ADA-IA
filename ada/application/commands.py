"""Exact command dispatcher shared by ADA interfaces."""

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass(frozen=True)
class Command:
    name: str
    handler: Callable[[], dict]
    requires_confirmation: bool = False


class CommandDispatcher:
    def __init__(self, commands: Dict[str, Command]):
        self._commands = {str(alias).lower(): command for alias, command in commands.items()}

    def dispatch(self, text: str) -> Optional[dict]:
        token = str(text or "").strip().split(maxsplit=1)[0].lower() if str(text or "").strip() else ""
        command = self._commands.get(token)
        if command is None:
            return None
        if command.requires_confirmation:
            return {"pending": command.name, "reply": f"¿Confirmás {command.name}? (sí/no)"}
        return command.handler()
