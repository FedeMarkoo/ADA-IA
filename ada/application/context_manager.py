"""Bounded, model-independent context packets for ADA conversations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-free estimate; real tokenizers remain optional."""
    value = str(text or "")
    return max(1, (len(value) + 3) // 4)


@dataclass
class ContextPacket:
    conversation_id: str
    summary: str = ""
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    memories: List[str] = field(default_factory=list)
    profile: List[str] = field(default_factory=list)
    task_state: Dict[str, Any] = field(default_factory=dict)
    token_budget: int = 4096
    estimated_tokens: int = 0
    truncated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        chunks = []
        if self.summary:
            chunks.append("RESUMEN:\n" + self.summary)
        if self.recent_messages:
            chunks.append(
                "CONVERSACIÓN RECIENTE:\n"
                + "\n".join(f"{item.get('role', 'assistant')}: {item.get('text', '')}" for item in self.recent_messages)
            )
        if self.memories:
            chunks.append("MEMORIA RELEVANTE:\n" + "\n".join(f"- {item}" for item in self.memories))
        if self.profile:
            chunks.append("PERFIL RELEVANTE:\n" + "\n".join(f"- {item}" for item in self.profile))
        if self.task_state:
            chunks.append("ESTADO DE TAREA:\n" + str(self.task_state))
        return "\n\n".join(chunks)


class ContextManager:
    def __init__(self, memory=None, config: Optional[Dict[str, Any]] = None):
        self.memory = memory
        self.config = config or {}

    def budget_for(self, role="chat", complexity=3, available_tokens=None) -> int:
        policy = self.config.get("context_policy") or {}
        role_policy = policy.get(role) or policy.get("chat") or {}
        configured = role_policy.get("token_budget") if isinstance(role_policy, dict) else role_policy
        if configured is None:
            configured = {"router": 4096, "chat": 8192, "coding": 16384, "reasoning": 24576, "tools": 8192}.get(
                role, 8192
            )
        budget = int(configured)
        if int(complexity or 3) <= 2:
            budget = min(budget, 4096)
        if available_tokens:
            budget = min(budget, max(1024, int(available_tokens)))
        return max(1024, budget)

    @staticmethod
    def _recent(messages: Iterable[Dict[str, Any]], budget: int) -> List[Dict[str, Any]]:
        result = []
        used = 0
        for item in reversed(list(messages)):
            cost = estimate_tokens(item.get("text", ""))
            if result and used + cost > budget:
                break
            result.insert(0, dict(item))
            used += cost
        return result

    def build(
        self, conversation_id="main", query="", messages=None, role="chat", complexity=3, task_state=None
    ) -> ContextPacket:
        budget = self.budget_for(role, complexity)
        source = list(messages or [])
        if not source and self.memory and hasattr(self.memory, "conversation"):
            source = self.memory.conversation(conversation_id, limit=100)
        summary = (
            self.memory.get_conversation_summary(conversation_id)
            if self.memory and hasattr(self.memory, "get_conversation_summary")
            else ""
        )
        memories = (
            self.memory.search_text(query, k=5) if query and self.memory and hasattr(self.memory, "search_text") else []
        )
        profile = (
            self.memory.knowledge(query, limit=3) if query and self.memory and hasattr(self.memory, "knowledge") else []
        )
        packet = ContextPacket(
            conversation_id=str(conversation_id),
            summary=str(summary or ""),
            recent_messages=self._recent(source, max(1024, budget // 2)),
            memories=[str(item) for item in memories[:5]],
            profile=[str(item) for item in profile[:3]],
            task_state=dict(task_state or {}),
            token_budget=budget,
        )
        rendered = packet.render()
        packet.estimated_tokens = estimate_tokens(rendered)
        if packet.estimated_tokens > budget:
            packet.memories = packet.memories[:2]
            packet.profile = packet.profile[:1]
            packet.recent_messages = self._recent(packet.recent_messages, max(1024, budget // 3))
            packet.truncated = True
            packet.estimated_tokens = estimate_tokens(packet.render())
        return packet

    def save_summary(self, conversation_id, summary):
        if self.memory and hasattr(self.memory, "save_conversation_summary"):
            self.memory.save_conversation_summary(conversation_id, str(summary or ""))
