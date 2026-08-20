"""Declarative model catalog and hardware tier definitions loaded from models/catalog.json."""

import json
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
        "name": "nomic-embed-text",
        "roles": ["embedding"],
        "quality_tier": "small",
        "min_ram_gb": 2,
        "description": "Modelo de embeddings de alto rendimiento para búsqueda semántica.",
    },
]


class ModelCatalog:
    """Provides filtered model recommendations based on models/catalog.json and hardware profile."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Return the declarative model catalog with hardware suitability flags."""
        profile = hardware_profile()
        ram_gb = profile.get("ram_gb", 8)
        raw_catalog = self.config.get("model_catalog")

        if not raw_catalog and CATALOG_PATH.is_file():
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_catalog = data.get("models")
            except Exception:
                pass

        if not raw_catalog:
            raw_catalog = DEFAULT_MODEL_CATALOG

        if isinstance(raw_catalog, dict):
            raw_catalog = [dict({"name": name}, **value) for name, value in raw_catalog.items()]

        result = []
        for item in raw_catalog:
            min_ram = item.get("min_ram_gb", 4)
            entry = dict(item)
            entry["hardware_fit"] = ram_gb >= min_ram
            entry["recommended"] = ram_gb >= (min_ram + 2)
            result.append(entry)
        return result

    def get_roles(self) -> List[str]:
        """Return available standard model roles."""
        return ["chat", "vision", "router", "tools", "embedding", "reasoning"]
