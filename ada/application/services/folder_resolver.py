"""Fast, contextual folder resolution for natural-language file requests."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import unicodedata
from pathlib import Path


class FolderResolver:
    """Resolve human folder references without blocking a web worker on GVFS."""

    STOPWORDS = {
        "cual", "es", "la", "el", "las", "los", "de", "del", "en", "que", "hay",
        "tenes", "tienes", "tengo", "tiene", "tienen", "tu", "tus", "fotos", "foto", "archivos",
        "archivo", "carpeta", "carpetas", "directorios", "directorio", "ruta", "donde",
        "quiero", "saber", "busca", "buscar", "buscame", "mostrame", "mostrar", "listame", "lista",
        "listar", "sea", "ahi", "adentro", "dentro", "contenido", "contenidos", "una", "un",
        "y", "por", "favor", "cuanto", "cuantos", "cuanta", "cuantas", "cantidad", "total",
        "estan", "esta", "estaba", "estaban", "me", "acuerdo", "refiero", "exacta", "exacto",
        "che", "ada", "no", "mis", "mi", "cumple", "cumpleanos",
    }

    def __init__(self, config, memory=None):
        self.config = config or {}
        self.memory = memory

    @staticmethod
    def _normalize(value):
        value = unicodedata.normalize("NFKD", str(value).casefold())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", value)).strip()

    def _base(self):
        return Path(os.path.abspath(os.path.expanduser(str(self.config.get("base_dir") or "~/GoogleDrive"))))

    def _key(self, text):
        return self._normalize(text)

    def _terms(self, text):
        return [term for term in self._key(text).split() if term not in self.STOPWORDS and len(term) > 1]

    def _inside_base(self, path):
        try:
            Path(path).absolute().relative_to(self._base())
            return True
        except ValueError:
            return False

    def _children(self, parent, deadline):
        """List one directory level in a killable subprocess."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return []
        timeout = max(0.1, min(float(self.config.get("folder_probe_timeout", 0.75)), remaining))
        process = None
        output = b""
        try:
            process = subprocess.Popen(
                ["ls", "-1A", "--quoting-style=literal", "--", str(parent)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            try:
                output, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                output = error.output or b""
                process.kill()
                # Never wait here: a process blocked in uninterruptible mount
                # I/O may ignore SIGKILL until the kernel call returns.
                threading.Thread(target=process.wait, daemon=True).start()
        except OSError:
            if process and process.poll() is None:
                process.kill()
            return []
        names = output.decode("utf-8", errors="replace").splitlines()
        return [Path(parent) / name for name in names if name and not name.startswith(".")]

    def _is_directory(self, path):
        """Check a cached path without letting a remote mount block the worker."""
        process = None
        timeout = max(0.1, float(self.config.get("folder_probe_timeout", 0.75)))
        try:
            process = subprocess.Popen(
                ["test", "-d", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.wait(timeout=timeout)
            return process.returncode == 0
        except subprocess.TimeoutExpired:
            process.kill()
            threading.Thread(target=process.wait, daemon=True).start()
            return False
        except OSError:
            if process and process.poll() is None:
                process.kill()
            return False

    def _score(self, path, terms):
        name = self._normalize(path.name)
        phrase = " ".join(terms)
        if name == phrase:
            return 100.0
        aliases = {"15": ("15", "xv")}
        matches = [any(value in name for value in aliases.get(term, (term,))) for term in terms]
        if all(matches):
            return 50.0 + sum(len(term) / max(1, len(name)) for term in terms)
        return sum(1 for matched in matches if matched) / max(1, len(terms))

    def _candidates(self, terms, context_path=None):
        started = time.monotonic()
        deadline = started + max(1.0, float(self.config.get("folder_resolver_timeout", 4.0)))
        base = self._base()
        context = Path(context_path).absolute() if context_path and self._inside_base(context_path) else None
        scanned = []
        candidates = {}
        max_probes = max(4, int(self.config.get("folder_max_probes", 40)))

        def scan(parent):
            parent = Path(parent)
            key = str(parent)
            if key in scanned or len(scanned) >= max_probes or time.monotonic() >= deadline:
                return []
            scanned.append(key)
            children = self._children(parent, deadline)
            for child in children:
                score = self._score(child, terms)
                if score >= 1.0:
                    candidates[str(child)] = max(score, candidates.get(str(child), 0.0))
            return children

        context_children = scan(context) if context else []
        if not any(score >= 100 for score in candidates.values()):
            base_children = context_children if context == base else scan(base)
            photo_root = Path(os.path.expanduser(str(self.config.get("photo_root") or base / "Fotos")))
            roots = list(base_children)
            roots.sort(key=lambda path: (
                0 if path == photo_root or self._normalize(path.name) == "fotos" else
                1 if self._normalize(path.name) in {"documentos", "pictures", "photos"} else 2,
                self._normalize(path.name),
            ))
            next_level = []
            for root in roots:
                if time.monotonic() >= deadline or any(score >= 100 for score in candidates.values()):
                    break
                next_level.extend(scan(root))
            if not any(score >= 100 for score in candidates.values()):
                next_level.sort(key=lambda path: (
                    0 if any(word in self._normalize(path.name) for word in ("evento", "sesion", "foto", "cobertura")) else 1,
                    self._normalize(path.name),
                ))
                for root in next_level:
                    if time.monotonic() >= deadline or any(score >= 100 for score in candidates.values()):
                        break
                    scan(root)

        ordered = sorted(candidates.items(), key=lambda item: (-item[1], self._normalize(Path(item[0]).name), item[0]))
        return [Path(path) for path, _ in ordered[:8]], {
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "scanned_roots": scanned,
            "timed_out": time.monotonic() >= deadline,
        }

    def resolve(self, text, context_path=None):
        started = time.monotonic()
        key = self._key(text)
        terms = self._terms(text)
        base = self._base()
        named_terms = [term for term in terms if term not in {"google", "drive", "gdrive"}]
        stale_paths = []

        if re.search(r"\b(root|raiz|base|principal)\b", key) or (
            re.search(r"\b(gdrive|google drive|drive)\b", key)
            and re.search(r"\b(que|todas?|carpetas?|tengo|hay)\b", key)
            and not named_terms
        ):
            return {"status": "resolved", "path": str(base), "source": "configured_base", "confidence": 1.0,
                    "elapsed_ms": round((time.monotonic() - started) * 1000), "terms": terms}

        # "en Google Drive" describes the search root, not part of a folder
        # name. When the user also supplies a proper label (for example
        # "Sofía"), search by that label only.
        terms = named_terms or terms
        canonical = " ".join(terms)

        if (
            terms
            and context_path
            and self._inside_base(context_path)
            and self._score(Path(context_path), terms) >= 1.0
            and self._is_directory(context_path)
        ):
            return {
                "status": "resolved",
                "path": str(Path(context_path).absolute()),
                "source": "session_context_match",
                "confidence": 0.99,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "terms": terms,
            }

        if self.memory:
            for alias_key in (canonical,):
                if not alias_key:
                    continue
                alias = self.memory.get_folder_alias(alias_key)
                if alias and self._inside_base(alias["path"]) and self._is_directory(alias["path"]):
                    return {"status": "resolved", "path": alias["path"], "source": "memory",
                            "confidence": alias["confidence"], "elapsed_ms": round((time.monotonic() - started) * 1000),
                            "terms": terms}
                if alias and self._inside_base(alias["path"]):
                    stale_paths.append(alias["path"])

            if canonical and hasattr(self.memory, "search_folders"):
                indexed = self.memory.search_folders(terms, limit=20)
                available = []
                for item in indexed:
                    if self._inside_base(item["path"]) and self._is_directory(item["path"]):
                        available.append(item)
                    elif self._inside_base(item["path"]):
                        stale_paths.append(item["path"])
                indexed = available
                if context_path and self._inside_base(context_path):
                    contextual = [
                        item for item in indexed
                        if Path(item["path"]).absolute() == Path(context_path).absolute()
                        or Path(context_path).absolute() in Path(item["path"]).absolute().parents
                    ]
                    if contextual:
                        indexed = contextual
                exact = [item for item in indexed if self._normalize(item["name"]) == canonical]
                if len(exact) == 1:
                    indexed = exact
                if len(indexed) == 1:
                    path = indexed[0]["path"]
                    self.memory.save_folder_alias(canonical, path, 0.97)
                    return {"status": "resolved", "path": path, "source": "folder_index", "confidence": 0.97,
                            "elapsed_ms": round((time.monotonic() - started) * 1000), "terms": terms}
                if indexed:
                    return {"status": "ambiguous", "candidates": [item["path"] for item in indexed[:8]],
                            "source": "folder_index", "elapsed_ms": round((time.monotonic() - started) * 1000),
                            "terms": terms}

        if not terms:
            if context_path and self._inside_base(context_path) and self._is_directory(context_path):
                return {"status": "resolved", "path": str(Path(context_path).absolute()), "source": "session_context",
                        "confidence": 0.9, "elapsed_ms": round((time.monotonic() - started) * 1000), "terms": []}
            return {"status": "none", "candidates": [], "reason": "no_folder_terms",
                    "elapsed_ms": round((time.monotonic() - started) * 1000), "terms": []}

        candidates, diagnostics = self._candidates(terms, context_path=context_path)
        exact = [path for path in candidates if self._normalize(path.name) == canonical]
        if len(exact) == 1:
            candidates = exact
        if len(candidates) == 1:
            path = str(candidates[0].absolute())
            if self.memory:
                if canonical:
                    self.memory.save_folder_alias(canonical, path, 0.98 if exact else 0.9)
            return {"status": "resolved", "path": path, "source": "folder_search",
                    "confidence": 0.98 if exact else 0.9, "terms": terms, **diagnostics}
        if candidates:
            return {"status": "ambiguous", "candidates": [str(path.absolute()) for path in candidates],
                    "terms": terms, **diagnostics}
        result = {"status": "none", "candidates": [], "reason": "not_found", "terms": terms, **diagnostics}
        if stale_paths:
            result["reason"] = "stale_index"
            result["stale_paths"] = list(dict.fromkeys(stale_paths))[:8]
        return result

    def resolve_label(self, label, context_path=None):
        """Resolve an explicit folder label, including otherwise generic names."""
        terms = [term for term in self._normalize(label).split() if term]
        if not terms:
            return {"status": "none", "candidates": [], "reason": "empty_label", "terms": []}
        candidates, diagnostics = self._candidates(terms, context_path=context_path)
        canonical = " ".join(terms)
        exact = [path for path in candidates if self._normalize(path.name) == canonical]
        if len(exact) == 1:
            path = str(exact[0].absolute())
            if self.memory:
                self.memory.save_folder_alias(canonical, path, 1.0)
            return {"status": "resolved", "path": path, "source": "folder_label", "confidence": 1.0,
                    "terms": terms, **diagnostics}
        if candidates:
            return {"status": "ambiguous", "candidates": [str(path.absolute()) for path in candidates],
                    "terms": terms, **diagnostics}
        return {"status": "none", "candidates": [], "reason": "not_found", "terms": terms, **diagnostics}
