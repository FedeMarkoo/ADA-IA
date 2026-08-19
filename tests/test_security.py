import unittest
import tempfile
from pathlib import Path

from src.ada.capabilities.system.run_script import run as script_run
from src.ada.infrastructure.runtime.resources import recommended_threads
from src.ada.capabilities.files.filesystem import run as filesystem_run


class SecurityTests(unittest.TestCase):
    def test_filesystem_rejects_path_outside_allowlist(self):
        result = filesystem_run({
            'action': 'list_files', 'dir': '/tmp', 'allowed_roots': ['/Users/home/Desktop'],
        })
        self.assertEqual(result['error'], 'path_outside_allowed_roots')

    def test_scripts_are_disabled_without_explicit_allowlist(self):
        result = script_run({'command': 'echo no'})
        self.assertEqual(result['error'], 'command_execution_disabled')

    def test_thread_budget_scales_with_cpu_budget(self):
        self.assertGreaterEqual(recommended_threads({'cpu_limit_percent': 100}), 1)

    def test_filesystem_supports_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            source.mkdir()
            (source / 'file.txt').write_text('data')
            result = filesystem_run({'action': 'move_files', 'source': source, 'name': 'target',
                                     'confirm': True, 'dry_run': True})
            self.assertTrue(result['dry_run'])
            self.assertTrue((source / 'file.txt').exists())
            self.assertFalse((Path(directory) / 'target').exists())


if __name__ == '__main__':
    unittest.main()
