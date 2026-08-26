"""Bounded, model-independent compaction for long conversation histories."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


class MemoryCompactor:
    """Replace old message rows with a bounded extractive summary.

    Compaction is deliberately model-independent: it never sends private history
    to an external provider and it remains available when no model is configured.
    """

    def __init__(self, memory, config: Dict[str, Any] | None = None):
        self.memory = memory
        self.config = config or {}

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("memory_compaction_enabled", True))

    @property
    def threshold_messages(self) -> int:
        return max(20, int(self.config.get("memory_compaction_threshold_messages", 100)))

    @property
    def keep_messages(self) -> int:
        return max(4, int(self.config.get("memory_compaction_keep_messages", 40)))

    @property
    def max_summary_chars(self) -> int:
        return max(500, int(self.config.get("memory_compaction_max_summary_chars", 6000)))

    def compact_sessions(self, sessions: Iterable[str]) -> Dict[str, int]:
        if not self.enabled or not hasattr(self.memory, "compact_conversation"):
            return {"sessions": 0, "messages": 0}
        compacted_sessions = 0
        compacted_messages = 0
        for session in sessions:
            # Read the complete session before deleting rows; otherwise an older
            # prefix could be removed without ever entering the summary.
            messages = self.memory.conversation(session=session, limit=100_000)
            if len(messages) <= self.threshold_messages:
                continue
            old_messages = messages[: -self.keep_messages]
            summary = self._summary(self.memory.get_conversation_summary(session), old_messages)
            removed = self.memory.compact_conversation(session, summary, self.keep_messages)
            if removed:
                compacted_sessions += 1
                compacted_messages += removed
        return {"sessions": compacted_sessions, "messages": compacted_messages}

    def _summary(self, existing: str, messages: List[Dict[str, Any]]) -> str:
        lines = [line.strip() for line in str(existing or "").splitlines() if line.strip()]
        seen = set(lines)
        for message in messages:
            text = " ".join(str(message.get("text", "")).split())
            if not text:
                continue
            # Keep useful context without allowing one huge message to defeat the bound.
            text = text[:400] + ("…" if len(text) > 400 else "")
            line = f"{message.get('role', 'assistant')}: {text}"
            if line not in seen:
                lines.append(line)
                seen.add(line)
        result = "\n".join(lines)
        if len(result) > self.max_summary_chars:
            result = result[: self.max_summary_chars]
            result = result.rsplit("\n", 1)[0]
        return result
