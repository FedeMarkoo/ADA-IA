from pathlib import Path
import importlib.util


def load_skills():
    skills = {}
    base = Path(__file__).parent
    for p in sorted(base.rglob('*.py')):
        if p.name == '__init__.py':
            continue
        name = p.stem
        module_name = f"ada_skill_{name}"
        spec = importlib.util.spec_from_file_location(module_name, str(p))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, 'run'):
                    skills[name] = mod.run
            except Exception:
                # skip modules that fail to import
                continue
    return skills
