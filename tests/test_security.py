import unittest

from src.ada.capabilities.files.filesystem import run as filesystem_run
from src.ada.capabilities.system.run_script import run as script_run
from src.ada.infrastructure.runtime.resources import recommended_threads


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


if __name__ == '__main__':
    unittest.main()
