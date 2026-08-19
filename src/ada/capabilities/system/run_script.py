import subprocess
import shlex
import os

def run(args):
    """Run a command without a shell and return an execution report."""
    cmd = args.get('command')
    timeout = max(1, min(int(args.get('timeout', 60)), 3600))
    if not cmd:
        return {'error': 'no command provided'}
    parts = shlex.split(cmd)
    allowed = args.get('allowed_commands') or os.environ.get('ADA_ALLOWED_COMMANDS', '').split(',')
    allowed = {item.strip() for item in allowed if item.strip()}
    if not allowed:
        return {'error': 'command_execution_disabled', 'message': 'Configurá allowed_commands para habilitar scripts.'}
    if not parts or parts[0] not in allowed:
        return {'error': 'command_not_allowed', 'command': parts[0] if parts else ''}
    try:
        # shlex split for safety
        proc = subprocess.run(
            parts, capture_output=True, text=True, timeout=timeout,
            cwd=args.get('cwd') or None
        )
        return {
            'ok': proc.returncode == 0,
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'command': cmd,
            'timeout_seconds': timeout,
        }
    except subprocess.TimeoutExpired:
        return {'error': 'timeout'}
    except Exception as e:
        return {'error': str(e)}
