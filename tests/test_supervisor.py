import unittest

from ada.infrastructure.runtime.supervisor import ServiceSupervisor


class SupervisorTests(unittest.TestCase):
    def test_supervisor_keeps_named_targets_without_starting_them(self):
        def target():
            return None

        supervisor = ServiceSupervisor({"web": target, "autonomy": target})
        self.assertEqual(set(supervisor.targets), {"web", "autonomy"})
        self.assertFalse(supervisor.processes)


if __name__ == "__main__":
    unittest.main()
