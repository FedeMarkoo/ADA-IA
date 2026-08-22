"""Background Memory & Context Refiner for ADA.

Periodically:
1. Analyzes recent conversation sessions, identifying user corrections, confirmations,
   and successful answers to synthesize durable semantic knowledge and procedures.
2. Identifies and removes outdated or stale episodic memories and redundant tasks.
3. Keeps context and knowledge sharp, up-to-date and compact.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ada.memory_refiner")


class MemoryRefiner:
    def __init__(self, memory, agent=None, config: Optional[Dict[str, Any]] = None):
        self.memory = memory
        self.agent = agent
        self.config = config or {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_run: float = 0.0

    @property
    def interval_seconds(self) -> int:
        # Default is 10 minutes (600s), configurable in config.json under "memory_refiner_interval_seconds"
        configured = self.config.get("memory_refiner_interval_seconds")
        if configured is not None:
            try:
                return max(60, int(configured))
            except (TypeError, ValueError):
                pass
        return 600

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("memory_refiner_enabled", True))

    @property
    def max_memory_age_days(self) -> int:
        configured = self.config.get("memory_max_age_days")
        try:
            return max(1, int(configured)) if configured else 30
        except (TypeError, ValueError):
            return 30

    def start(self) -> Optional[threading.Thread]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self._thread
            self._stop_event.clear()

            def loop():
                logger.info("memory_refiner_started interval=%ds", self.interval_seconds)
                # First run after 30 seconds of uptime to let system boot cleanly
                if self._stop_event.wait(30):
                    return
                while not self._stop_event.is_set():
                    try:
                        if self.enabled:
                            self.refine_cycle()
                    except Exception as exc:
                        logger.exception("memory_refiner_cycle_error: %s", exc)
                    if self._stop_event.wait(self.interval_seconds):
                        break

            self._thread = threading.Thread(target=loop, name="ada-memory-refiner", daemon=True)
            self._thread.start()
            return self._thread

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=5.0)
                if self._thread.is_alive():
                    logger.warning("memory_refiner thread did not stop within timeout")
                self._thread = None

    def refine_cycle(self) -> Dict[str, Any]:
        """Execute one complete refinement pass over conversations, knowledge, and memories."""
        extracted_facts = self._extract_knowledge_from_conversations()
        pruned_memories = self._prune_stale_memories()
        pruned_tasks = self._prune_old_tasks()
        with self._lock:
            self._last_run = time.time()
            current_time = self._last_run
        summary = {
            "extracted_facts": extracted_facts,
            "pruned_memories": pruned_memories,
            "pruned_tasks": pruned_tasks,
            "timestamp": current_time,
        }
        logger.info("memory_refiner_completed: %s", summary)
        return summary

    def _extract_knowledge_from_conversations(self) -> int:
        """Scan recent conversations for user preferences, facts, and corrections."""
        if not hasattr(self.memory, "conn") or not self.memory.conn:
            return 0

        # Retrieve distinct sessions
        try:
            sessions = [
                row[0] for row in self.memory.conn.execute(
                    "SELECT DISTINCT session FROM conversation_messages ORDER BY id DESC LIMIT 20"
                ).fetchall()
            ]
        except Exception:
            return 0

        total_extracted = 0
        for session in sessions:
            messages = self.memory.conversation(session=session, limit=40)
            if len(messages) < 2:
                continue

            extracted = self._analyze_session_messages(messages, session)
            total_extracted += extracted

        return total_extracted

    def _analyze_session_messages(self, messages: List[Dict[str, Any]], session: str) -> int:
        """Identify explicit corrections or confirmed knowledge patterns in message sequences."""
        count = 0
        for i in range(len(messages) - 1):
            user_msg = messages[i]
            if user_msg.get("role") != "user":
                continue
            assistant_msg = messages[i + 1] if i + 1 < len(messages) else {}
            if assistant_msg.get("role") != "assistant":
                continue

            u_text = user_msg.get("text", "").strip()
            a_text = assistant_msg.get("text", "").strip()

            # Pattern 1: User explicitly stating a preference / permanent fact
            # e.g., "mi nombre es Juan", "preferí siempre formato markdown", "guardo las fotos en ..."
            fact = self._detect_user_fact_or_preference(u_text)
            if fact:
                if not self._fact_already_known(fact):
                    self.memory.add_knowledge(
                        name=f"learned_pref_{time.time_ns()}_{count}",
                        content=fact,
                        source=f"conversation:{session}",
                    )
                    count += 1

            # Pattern 2: User correction (e.g. "no, en realidad...", "corregí eso...", "acordate que...")
            correction = self._detect_user_correction(u_text)
            if correction:
                if not self._fact_already_known(correction):
                    self.memory.add_knowledge(
                        name=f"learned_correction_{time.time_ns()}_{count}",
                        content=f"Corrección del usuario: {correction}",
                        source=f"conversation:{session}",
                    )
                    count += 1

        return count

    def _detect_user_fact_or_preference(self, text: str) -> Optional[str]:
        """Detect direct user facts or permanent system preferences."""
        patterns = [
            r"\b(?:mi|mis)\s+(?:nombre|cumpleaños|mail|correo|carpeta|directorio|preferencia|equipo)\s+(?:es|son)\s+([^\n\.\?]+)",
            r"\b(?:guard[ao]|descarg[ao]|almacen[ao])\s+(?:siempre\s+)?(?:los|las|mis)?\s*(?:fotos?|archivos?|documentos?)\s+en\s+([^\n\.\?]+)",
            r"\bprefer(?:ir[ií]a|o)\s+(?:siempre\s+)?(?:que\s+)?([^\n\.\?]+)",
            r"\brecord[aá]\s+(?:que\s+)?([^\n\.\?]+)",
            r"\bacordate\s+(?:que\s+)?([^\n\.\?]+)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                clean_fact = text.strip()
                if 8 <= len(clean_fact) <= 300:
                    return clean_fact
        return None

    def _detect_user_correction(self, text: str) -> Optional[str]:
        """Detect user feedback fixing a prior misunderstanding."""
        low = text.lower()
        if low.startswith(("no, ", "no ", "te equivocaste", "está mal", "incorrecto", "en realidad ")):
            clean = text.strip()
            if 10 <= len(clean) <= 300 and not clean.endswith("?"):
                return clean
        return None

    def _fact_already_known(self, fact: str) -> bool:
        """Check if identical or highly similar fact is already in memory."""
        try:
            existing = self.memory.knowledge(fact, limit=3)
            fact_low = fact.lower()
            for doc in existing:
                if fact_low in doc.lower() or doc.lower() in fact_low:
                    return True
        except Exception:
            pass
        return False

    def _prune_stale_memories(self) -> int:
        """Remove old, unreferenced notes or transient task results beyond max_memory_age_days."""
        if not hasattr(self.memory, "conn") or not self.memory.conn:
            return 0
        try:
            with self.memory._lock:
                cutoff_days = self.max_memory_age_days
                # Prune transient notes / task_results older than cutoff days, preserving 'knowledge'
                cursor = self.memory.conn.execute(
                    "DELETE FROM memories WHERE kind IN ('note', 'task_result') "
                    "AND created_at < datetime('now', ?)",
                    (f"-{cutoff_days} days",),
                )
                self.memory.conn.commit()
                return cursor.rowcount
        except Exception as exc:
            logger.warning("prune_stale_memories_failed: %s", exc)
            return 0

    def _prune_old_tasks(self) -> int:
        """Purge old executed tasks to keep memory DB size lean."""
        try:
            return self.memory.purge_tasks(keep=500)
        except Exception:
            return 0
