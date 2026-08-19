"""Layered memory facade over the persistent store."""

from dataclasses import dataclass
from src.ada.infrastructure.providers import MemoryStore


@dataclass
class MemoryLayers:
    store: MemoryStore

    def remember(self, content, layer="episodic", meta=None):
        allowed = {"short_term", "episodic", "semantic", "profile"}
        if layer not in allowed:
            raise ValueError(f"Capa de memoria inválida: {layer}")
        self.store.add_text(content, meta=meta, kind=layer)

    def recall(self, query, limit=5, layers=None):
        if not layers:
            return self.store.search_text(query, k=limit)
        results = []
        for layer in layers:
            results.extend(self.store.search_text(query, k=limit, kind=layer))
        return results[:limit]

    def profile(self, query, limit=3):
        return self.store.knowledge(query, limit=limit)

    def compact(self, max_tasks=1000):
        purge = getattr(self.store, "purge_tasks", None)
        return purge(max_tasks) if purge else 0
