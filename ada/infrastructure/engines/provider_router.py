"""Policy router for model providers inspired by Hermes Agent.

The router is deliberately provider-agnostic: it ranks configured providers
by privacy, remaining token budget, price and observed latency. It does not
create credentials or silently enable a cloud provider.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Iterable, Optional


class ProviderRouter:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._lock = threading.RLock()
        self._usage: Dict[str, int] = {}

    def _profiles(self) -> list[Dict[str, Any]]:
        configured = (self.config.get("provider_router") or {}).get("providers") or []
        if isinstance(configured, dict):
            configured = [dict(value, name=name) for name, value in configured.items()]
        return [item for item in configured if isinstance(item, dict) and item.get("name")]

    def _remaining(self, profile: Dict[str, Any]) -> Optional[int]:
        limit = profile.get("monthly_token_limit")
        if limit is None:
            return None
        try:
            return max(0, int(limit) - self._usage.get(str(profile["name"]), 0))
        except (TypeError, ValueError):
            return None

    def record(self, provider: str, tokens: int) -> None:
        with self._lock:
            self._usage[provider] = self._usage.get(provider, 0) + max(0, int(tokens or 0))

    def usage(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._usage)

    def choose(self, task: Dict[str, Any], available: Dict[str, bool], fallback: Iterable[str]) -> Optional[str]:
        requested = str(task.get("model_provider") or task.get("provider") or "").strip().lower()
        if requested and available.get(requested):
            return requested

        privacy = str(task.get("privacy", self.config.get("privacy_default", "normal"))).lower()
        estimate = max(1, int(task.get("estimated_tokens") or task.get("max_tokens") or 512))
        profiles = self._profiles()
        candidates = []
        for index, profile in enumerate(profiles):
            name = str(profile["name"]).lower()
            if not available.get(name):
                continue
            if privacy == "high" and not bool(profile.get("local", name in {"ollama", "local", "gpt4all"})):
                continue
            remaining = self._remaining(profile)
            if remaining is not None and remaining < estimate:
                continue
            sort = str(profile.get("sort", (self.config.get("provider_router") or {}).get("sort", "balanced")))
            price = float(profile.get("price_per_million_tokens", 0) or 0)
            latency = float(profile.get("latency_ms", 1000) or 1000)
            priority = float(profile.get("priority", 0) or 0)
            score = priority * 100
            if sort == "price":
                score -= price * 10
            elif sort == "latency":
                score -= latency / 100
            else:
                score -= price * 3 + latency / 300
            candidates.append((score, -index, name))
        if candidates:
            return max(candidates)[2]

        for name in fallback:
            normalized = str(name).lower()
            if available.get(normalized):
                return normalized
        return None
