"""Central policy engine for permissions, confirmation and filesystem scope."""
import os
import shlex
from pathlib import Path


class PolicyViolation(ValueError):
    pass


class PolicyEngine:
    def __init__(self, config=None):
        self.config = config or {}
        roots = self.config.get('allowed_roots') or [self.config.get('photo_root'), Path.home() / 'Desktop']
        self.allowed_roots = [self._path(item) for item in roots if item]
        self.allowed_commands = set(self.config.get('allowed_commands', []))

    @staticmethod
    def _path(value):
        return Path(os.path.expanduser(str(value))).resolve()

    def path_allowed(self, value):
        if not self.allowed_roots:
            return True
        candidate = self._path(value)
        return any(candidate == root or root in candidate.parents for root in self.allowed_roots)

    def validate_paths(self, values):
        invalid = [str(value) for value in values if value and not self.path_allowed(value)]
        if invalid:
            raise PolicyViolation(f'Rutas fuera de la allowlist: {invalid}')

    def validate_command(self, command):
        parts = shlex.split(str(command or ''))
        if not parts:
            raise PolicyViolation('No se especificó ningún comando.')
        if self.allowed_commands and parts[0] not in self.allowed_commands:
            raise PolicyViolation(f'Binario no permitido: {parts[0]}')
        if not self.allowed_commands:
            raise PolicyViolation('La ejecución de comandos está deshabilitada.')

    def requires_confirmation(self, action, arguments=None):
        arguments = arguments or {}
        if action in {'gmail_send', 'instagram_publish', 'run_script', 'group_files', 'organize_photos', 'mcp'}:
            return True
        if action == 'filesystem' and arguments.get('action') in {'move_files', 'copy_files', 'mkdir'}:
            return True
        if action == 'lightroom' and arguments.get('action') in {'organize', 'organizar', 'mover', 'limpiar', 'recuperar'}:
            return True
        return False

    def authorize(self, action, arguments=None, confirmed=False):
        arguments = arguments or {}
        if action == 'run_script':
            self.validate_command(arguments.get('command'))
        paths = [arguments.get(key) for key in ('path', 'dir', 'source', 'image', 'script', 'cwd')]
        self.validate_paths(paths)
        if self.requires_confirmation(action, arguments) and self.config.get('confirm_risky', True) and not confirmed:
            raise PolicyViolation('confirmation_required')
