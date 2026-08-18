import subprocess
import shlex

def run(args):
    """Run a command without a shell and return an execution report."""
    cmd = args.get('command')
    timeout = max(1, min(int(args.get('timeout', 60)), 3600))
    if not cmd:
        return {'error': 'no command provided'}
    try:
        # shlex split for safety
        proc = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True, timeout=timeout,
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
