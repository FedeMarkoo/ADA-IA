"""Discover and load executable ADA capabilities."""
from pathlib import Path
import importlib.util


def load_capabilities():
    capabilities = {}
    base = Path(__file__).parent
    for path in sorted(base.rglob('*.py')):
        if path.name in {'__init__.py', 'registry.py'}:
            continue
        name = path.stem
        spec = importlib.util.spec_from_file_location(f'ada_capability_{name}', str(path))
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        if hasattr(module, 'run'):
            capabilities[name] = module.run
    return capabilities
