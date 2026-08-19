"""Layered memory facade over the persistent store."""
from dataclasses import dataclass


@dataclass
class MemoryLayers:
    store: object

    def remember(self, content, layer='episodic', meta=None):
        allowed = {'short_term', 'episodic', 'semantic', 'profile'}
        if layer not in allowed:
            raise ValueError(f'Capa de memoria inválida: {layer}')
        self.store.add_text(content, meta=meta, kind=layer)

    def recall(self, query, limit=5, layers=None):
        results = self.store.search_text(query, k=max(limit * 3, limit))
        if not layers:
            return results[:limit]
        # The backing store returns content only; use its lexical search for compatibility.
        return results[:limit]

    def profile(self, query, limit=3):
        return self.store.knowledge(query, limit=limit)

    def compact(self, max_tasks=1000):
        purge = getattr(self.store, 'purge_tasks', None)
        return purge(max_tasks) if purge else 0
