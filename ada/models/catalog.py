"""Declarative model catalog and hardware tier definitions with SQLite persistence."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from ada.infrastructure.runtime.resources import hardware_profile


def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _find_project_root()
CATALOG_PATH = PROJECT_ROOT / "models" / "catalog.json"
DEFAULT_DB_PATH = Path.home() / "Desktop" / "ADA_Data" / "configurations.db"

DEFAULT_MODEL_CATALOG = [
    {
        "name": "llama3.2:1b",
        "roles": ["router", "fast"],
        "quality_tier": "tiny",
        "min_ram_gb": 2,
        "description": "Ultrarrápido y liviano para clasificación de intents y tareas simples.",
    },
    {
        "name": "llama3.2:3b",
        "roles": ["chat", "router"],
        "quality_tier": "small",
        "min_ram_gb": 4,
        "description": "Equilibrio ideal entre velocidad y razonamiento para el día a día.",
    },
    {
        "name": "qwen2.5:3b",
        "roles": ["chat", "router"],
        "quality_tier": "small",
        "min_ram_gb": 4,
        "description": "Excelente seguimiento de instrucciones y código ligero.",
    },
    {
        "name": "qwen2.5:7b",
        "roles": ["chat", "tools", "coding"],
        "quality_tier": "medium",
        "min_ram_gb": 8,
        "description": "Potente modelo para tool-calling, código y razonamiento complejo.",
    },
    {
        "name": "qwen2.5vl:3b",
        "roles": ["vision"],
        "quality_tier": "small",
        "min_ram_gb": 6,
        "description": "Comprensión visual y OCR para fotos, documentos y capturas.",
    },
    {
        "name": "deepseek-r1:8b",
        "roles": ["chat", "reasoning"],
        "quality_tier": "medium",
        "min_ram_gb": 10,
        "description": "Capacidades avanzadas de razonamiento paso a paso (Chain of Thought).",
    },
    {
        "name": "deepseek-r1:14b",
        "roles": ["chat", "reasoning"],
        "quality_tier": "large",
        "min_ram_gb": 12,
        "description": "Razonamiento multi-paso avanzado de alta fidelidad.",
    },
    {
        "name": "deepseek-r1:32b",
        "roles": ["chat", "reasoning"],
        "quality_tier": "huge",
        "min_ram_gb": 24,
        "description": "Razonamiento agéntico profundo de máxima capacidad (~Claude Sonnet).",
    },
    {
        "name": "qwen2.5-coder:14b",
        "roles": ["coding", "tools", "chat"],
        "quality_tier": "large",
        "min_ram_gb": 12,
        "description": "Coding agéntico sólido y generación estructurada de código.",
    },
    {
        "name": "qwen2.5-coder:32b",
        "roles": ["coding", "tools", "chat"],
        "quality_tier": "huge",
        "min_ram_gb": 24,
        "description": "Coding agéntico de nivel superior para arquitectura y refactorización masiva.",
    },
    {
        "name": "deepseek-coder-v2:16b",
        "roles": ["coding", "tools", "chat"],
        "quality_tier": "large",
        "min_ram_gb": 12,
        "description": "Modelo de arquitectura MoE especializado en desarrollo y código.",
    },
    {
        "name": "qwen3:8b",
        "roles": ["chat", "general"],
        "quality_tier": "medium",
        "min_ram_gb": 8,
        "description": "Modelo general y de gestión para texto, finanzas y tareas diarias.",
    },
    {
        "name": "qwen3-coder:30b",
        "roles": ["coding", "tools", "chat"],
        "quality_tier": "huge",
        "min_ram_gb": 22,
        "description": "Modelo entrenado con RL para agentes autónomos y desarrollo avanzado.",
    },
    {
        "name": "gemma4:26b",
        "roles": ["tools", "chat"],
        "quality_tier": "huge",
        "min_ram_gb": 18,
        "description": "Tool calling nativo y agente general de Google.",
    },
    {
        "name": "gemma4:31b",
        "roles": ["tools", "chat"],
        "quality_tier": "huge",
        "min_ram_gb": 22,
        "description": "Tool calling y agente general avanzado de alta capacidad.",
    },
    {
        "name": "nomic-embed-text",
        "roles": ["embedding"],
        "quality_tier": "small",
        "min_ram_gb": 2,
        "description": "Modelo de embeddings de alto rendimiento para búsqueda semántica.",
    },
]


class ModelCatalog:
    """Provides filtered model recommendations backed by SQLite (models.db) with hardware suitability."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, db_path: Optional[Path] = None):
        self.config = config or {}
        self.db_path = Path(
            db_path
            or self.config.get("configurations_db_path")
            or self.config.get("database_paths", {}).get("configurations")
            or self.config.get("models_db_path")
            or DEFAULT_DB_PATH
        )
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """Ensure SQLite schema exists and bootstrap initial catalog from catalog.json if empty."""
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS model_catalog (
                        name TEXT PRIMARY KEY,
                        roles TEXT NOT NULL,
                        quality_tier TEXT DEFAULT 'medium',
                        min_ram_gb REAL DEFAULT 4,
                        description TEXT DEFAULT '',
                        auto_pull INTEGER DEFAULT 0,
                        priority INTEGER DEFAULT 100,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                conn.commit()

                # Check if catalog table is empty
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM model_catalog")
                count = cursor.fetchone()[0]

                if count == 0:
                    # Seed from catalog.json or DEFAULT_MODEL_CATALOG
                    models_to_seed = []
                    configured = self.config.get("model_catalog")
                    if configured:
                        if isinstance(configured, dict):
                            configured = [dict({"name": name}, **value) for name, value in configured.items()]
                        models_to_seed = configured
                    if CATALOG_PATH.is_file():
                        try:
                            if models_to_seed:
                                raise ValueError("configured catalog already loaded")
                            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                models_to_seed = data.get("models", [])
                        except Exception:
                            models_to_seed = DEFAULT_MODEL_CATALOG
                    else:
                        models_to_seed = DEFAULT_MODEL_CATALOG

                    for m in models_to_seed:
                        roles_str = json.dumps(m.get("roles", []))
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO model_catalog (name, roles, quality_tier, min_ram_gb, description)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                m.get("name"),
                                roles_str,
                                m.get("quality_tier", "medium"),
                                m.get("min_ram_gb", 4),
                                m.get("description", ""),
                            ),
                        )
                    conn.commit()

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Return all models from SQLite with hardware suitability calculation."""
        profile = hardware_profile()
        ram_gb = profile.get("ram_gb", 8)
        # Preserve the lightweight standalone API used by integrations and
        # tests. The full Agent config always supplies database_paths and
        # therefore uses configurations.db as the source of truth.
        configured = self.config.get("model_catalog")
        if configured and not self.config.get("database_paths") and not self.config.get("configurations_db_path"):
            if isinstance(configured, dict):
                configured = [dict({"name": name}, **value) for name, value in configured.items()]
            result = []
            for item in configured:
                entry = dict(item)
                min_ram = float(entry.get("min_ram_gb", 4))
                entry["min_ram_gb"] = min_ram
                entry["hardware_fit"] = ram_gb >= min_ram
                entry["recommended"] = ram_gb >= (min_ram + 2)
                result.append(entry)
            return result
        with self._lock:
            with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM model_catalog ORDER BY min_ram_gb ASC, name ASC")
                rows = cursor.fetchall()

                result = []
                for row in rows:
                    roles = []
                    try:
                        roles = json.loads(row["roles"])
                    except Exception:
                        roles = [r.strip() for r in str(row["roles"]).split(",") if r.strip()]

                    min_ram = float(row["min_ram_gb"] or 4)
                    entry = {
                        "name": row["name"],
                        "roles": roles,
                        "quality_tier": row["quality_tier"],
                        "min_ram_gb": min_ram,
                        "description": row["description"],
                        "auto_pull": bool(row["auto_pull"]),
                        "hardware_fit": ram_gb >= min_ram,
                        "recommended": ram_gb >= (min_ram + 2),
                    }
                    result.append(entry)
                return result

    def upsert_model(
        self,
        name: str,
        roles: List[str],
        description: str = "",
        quality_tier: str = "medium",
        min_ram_gb: float = 4,
        auto_pull: bool = False,
    ) -> Dict[str, Any]:
        """Add or update a model in the SQLite database catalog."""
        name = name.strip()
        roles_str = json.dumps(roles if isinstance(roles, list) else [roles])
        with self._lock:
            with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO model_catalog (name, roles, quality_tier, min_ram_gb, description, auto_pull, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                        roles=excluded.roles,
                        quality_tier=excluded.quality_tier,
                        min_ram_gb=excluded.min_ram_gb,
                        description=excluded.description,
                        auto_pull=excluded.auto_pull,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (name, roles_str, quality_tier, float(min_ram_gb), description, 1 if auto_pull else 0),
                )
                conn.commit()

        return {"ok": True, "name": name}

    def delete_model_from_catalog(self, name: str) -> bool:
        """Remove a model from the SQLite database catalog."""
        with self._lock:
            with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM model_catalog WHERE name = ?", (name,))
                conn.commit()
                return cursor.rowcount > 0

    def get_roles(self) -> List[str]:
        """Return available standard model roles."""
        return ["chat", "vision", "router", "tools", "embedding", "reasoning", "coding", "general"]
