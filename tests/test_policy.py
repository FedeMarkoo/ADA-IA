import os
from pathlib import Path
import unittest

from ada.domain.policy import PolicyEngine, PolicyViolation


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.allowed = [str(Path.home() / "Desktop"), str(Path.home() / "Pictures")]
        self.policy = PolicyEngine({"allowed_roots": self.allowed, "allowed_commands": ["ls", "python3"]})

    def test_path_allowed(self):
        desktop_file = str(Path.home() / "Desktop" / "test.txt")
        self.assertTrue(self.policy.path_allowed(desktop_file))

        # Disallowed path outside allowlist
        self.assertFalse(self.policy.path_allowed("/etc/shadow"))
        self.assertFalse(self.policy.path_allowed("/var/log"))
        self.assertFalse(self.policy.path_allowed(None))
        self.assertFalse(self.policy.path_allowed(""))

    def test_validate_paths_raises_violation(self):
        with self.assertRaises(PolicyViolation):
            self.policy.validate_paths(["/etc/passwd"])

    def test_validate_command(self):
        self.policy.validate_command("ls -la")
        self.policy.validate_command("python3 script.py")
        with self.assertRaises(PolicyViolation):
            self.policy.validate_command("rm -rf /")


if __name__ == "__main__":
    unittest.main()
