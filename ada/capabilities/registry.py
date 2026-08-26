import importlib.util
from dataclasses import dataclass
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("ada.capabilities")


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    risk_level: str = "low"
    permissions: tuple = ()
    argument_schema: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    version: str = "1.0"


class CapabilityLoadError(RuntimeError):
    """Raised when strict capability discovery finds a broken module."""


_RISKY = {
    "run_script",
    "group_files",
    "organize_photos",
    "filesystem",
    "mcp",
    "lightroom",
    "gmail_send",
    "gmail_draft",
    "instagram_publish",
}

_REGISTRY_LOCK = threading.RLock()
_LOADED_SPECS: Dict[str, Dict[str, Any]] = {}
_CACHED_CAPABILITIES: Optional[Dict[str, Callable]] = None
_CACHED_SPECS: Optional[Dict[str, CapabilitySpec]] = None
_LAST_DISCOVERED: float = 0.0


def load_capabilities(strict=False, force_reload=False):
    global _CACHED_CAPABILITIES, _LAST_DISCOVERED
    with _REGISTRY_LOCK:
        now = time.monotonic()
        if not force_reload and _CACHED_CAPABILITIES is not None and (now - _LAST_DISCOVERED < 15.0):
            return dict(_CACHED_CAPABILITIES)

        capabilities = {}
        _LOADED_SPECS.clear()
        base = Path(__file__).parent
        for path in sorted(base.rglob("*.py")):
            if path.name in {"__init__.py", "registry.py"}:
                continue
            relative_name = path.relative_to(base).with_suffix("").as_posix().replace("/", "_")
            spec = importlib.util.spec_from_file_location(f"ada_capability_{relative_name}", str(path))
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                logger.warning("capability_load_failed path=%s error=%s", path, exc)
                if strict:
                    raise CapabilityLoadError(f"Capability rota: {path}") from exc
                continue
            if getattr(module, "MCP_ONLY", False):
                continue
            if hasattr(module, "run"):
                declared = getattr(module, "CAPABILITY_SPEC", {})
                name = str(declared.get("name") or path.stem) if isinstance(declared, dict) else path.stem
                if name in capabilities:
                    raise CapabilityLoadError(f"Nombre de capability duplicado: {name}")
                capabilities[name] = module.run
                _LOADED_SPECS[name] = declared if isinstance(declared, dict) else {}
        _CACHED_CAPABILITIES = capabilities
        _LAST_DISCOVERED = now
        return capabilities


def capability_specs(force_reload=False):
    """Discover declarative metadata while preserving the callable registry API."""
    global _CACHED_SPECS
    with _REGISTRY_LOCK:
        if not force_reload and _CACHED_SPECS is not None and (time.monotonic() - _LAST_DISCOVERED < 15.0):
            return dict(_CACHED_SPECS)

        capabilities = load_capabilities(force_reload=force_reload)
        result = {}
        for name, function in capabilities.items():
            declared = _LOADED_SPECS.get(name, {})
            schema = declared.get("argument_schema", {"type": "object", "additionalProperties": True})
            if not isinstance(schema, dict):
                raise CapabilityLoadError(f"Schema de argumentos inválido para capability: {name}")
            risk = declared.get("risk_level", "high" if name in _RISKY else "low")
            if risk not in {"low", "medium", "high"}:
                raise CapabilityLoadError(f"risk_level inválido para capability: {name}")
            permissions = declared.get("permissions", ("filesystem.write",) if name in _RISKY else ())
            if isinstance(permissions, str):
                permissions = (permissions,)
            result[name] = CapabilitySpec(
                name=name,
                description=declared.get("description") or getattr(function, "__doc__", None) or f"Capability ADA: {name}",
                risk_level=risk,
                permissions=tuple(permissions),
                argument_schema=schema,
                requires_confirmation=bool(declared.get("requires_confirmation", name in _RISKY)),
                version=str(declared.get("version", "1.0")),
            )
        _CACHED_SPECS = result
        return result


def capability_catalog():
    """Return a JSON-serializable catalog for planners, UIs and MCP clients."""
    return {
        name: {
            "name": spec.name,
            "description": spec.description,
            "risk_level": spec.risk_level,
            "permissions": list(spec.permissions),
            "argument_schema": spec.argument_schema,
            "requires_confirmation": spec.requires_confirmation,
            "version": spec.version,
        }
        for name, spec in capability_specs().items()
    }
