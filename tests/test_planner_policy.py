import unittest

from src.ada.application.planner import Planner
from src.ada.domain.policy import PolicyEngine, PolicyViolation
from src.ada.domain.tasks import Action


class PlannerPolicyTests(unittest.TestCase):
    def test_policy_requires_confirmation_for_external_side_effects(self):
        policy = PolicyEngine({'allowed_roots': ['/tmp'], 'confirm_risky': True})
        with self.assertRaises(PolicyViolation):
            policy.authorize('gmail_send', {}, confirmed=False)
        policy.authorize('gmail_send', {}, confirmed=True)

    def test_policy_rejects_paths_outside_scope(self):
        policy = PolicyEngine({'allowed_roots': ['/tmp']})
        with self.assertRaises(PolicyViolation):
            policy.validate_paths(['/etc/passwd'])

    def test_planner_validates_capability_names(self):
        policy = PolicyEngine({'allowed_roots': ['/tmp']})
        planner = Planner({'list_files': lambda _: None}, policy)
        plan = planner.from_actions([Action('list_files', {'dir': '/tmp'})])
        self.assertTrue(plan.dry_run)
        with self.assertRaises(ValueError):
            planner.from_actions([Action('missing', {})])


if __name__ == '__main__':
    unittest.main()
