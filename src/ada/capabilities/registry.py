"""Discover and load executable ADA capabilities."""

from pathlib import Path
import importlib.util
from dataclasses import dataclass
import logging

logger = logging.getLogger("ada.capabilities")


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    risk_level: str = "low"
    permissions: tuple = ()


_RISKY = {
    "run_script",
    "group_files",
    "organize_photos",
    "filesystem",
    "mcp",
    "lightroom",
    "gmail_send",
    "instagram_publish",
}


def load_capabilities():
    capabilities = {}
    base = Path(__file__).parent
    for path in sorted(base.rglob("*.py")):
        if path.name in {"__init__.py", "registry.py"}:
            continue
        name = path.stem
        spec = importlib.util.spec_from_file_location(f"ada_capability_{name}", str(path))
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            logger.warning("capability_load_failed path=%s error=%s", path, exc)
            continue
        if hasattr(module, "run"):
            capabilities[name] = module.run
    return capabilities


def capability_specs():
    """Discover declarative metadata while preserving the callable registry API."""
    capabilities = load_capabilities()
    return {
        name: CapabilitySpec(
            name=name,
            description=getattr(function, "__doc__", None) or f"Capability ADA: {name}",
            risk_level="high" if name in _RISKY else "low",
            permissions=("filesystem.write",) if name in _RISKY else (),
        )
        for name, function in capabilities.items()
    }
