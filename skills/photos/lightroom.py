"""Safe adapter for the existing Lightroom photo manager.

ADA plans and simulates by default. Real operations are delegated to the
tested project script and require explicit confirmation.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT = ROOT / 'gestor_fotos_lightroom.py'
DEFAULT_RULES = ROOT / 'REGLAS_GESTOR_FOTOS.md'
DEFAULT_DB = ROOT / 'limpieza_lightroom.sqlite3'


def _run(command, timeout=3600):
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
        'command': command,
    }


def run(args):
    action = str(args.get('action', 'plan')).lower()
    root = Path(os.path.expanduser(args.get('root', '~/Desktop/Fotos'))).resolve()
    script = Path(os.path.expanduser(args.get('script', DEFAULT_SCRIPT))).resolve()
    db = Path(os.path.expanduser(args.get('db', DEFAULT_DB))).resolve()
    if action in {'status', 'estado', 'summary', 'resumen', 'structure', 'estructura', 'folders', 'carpetas'}:
        return {'error': 'SQLite queries belong to the sqlite tool, not the Lightroom manager.'}
    if not root.exists():
        return {'error': 'photo root not found', 'root': str(root)}
    if not script.exists():
        return {'error': 'manager script not found', 'script': str(script)}
    if action in {'organize', 'mover', 'limpiar', 'recuperar'} and not args.get('confirm'):
        return {'error': 'confirmation_required', 'action': action, 'root': str(root), 'message': 'Use plan/simulate first and confirm before changing Fotos.'}
    mode_map = {
        'count': 'contar',
        'analyze': 'analizar',
        'organize': 'organizar',
        'plan': 'organizar',
        'simulate': 'organizar',
        'organizar': 'organizar',
    }
    mode = mode_map.get(action, action)
    command = [sys.executable, str(script), '--modo', mode, '--root', str(root), '--db', str(db)]
    if action in {'plan', 'simulate'}:
        command.append('--simular')
    if args.get('include_sofia'):
        command.append('--incluir-sofia')
    if args.get('only_route'):
        command.extend(['--solo-ruta', str(Path(os.path.expanduser(args['only_route'])).resolve())])
    result = _run(command, timeout=int(args.get('timeout', 3600)))
    result.update({'skill': 'lightroom', 'action': action, 'root': str(root), 'safe_mode': action in {'plan', 'simulate'}})
    return result
