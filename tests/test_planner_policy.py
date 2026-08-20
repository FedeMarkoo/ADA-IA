import unittest

from ada.application.planner import Planner
from ada.capabilities.registry import capability_catalog
from ada.domain.policy import PolicyEngine, PolicyViolation
from ada.domain.tasks import Action
from ada.application.services.chat import ChatService


class PlannerPolicyTests(unittest.TestCase):
    def test_policy_requires_confirmation_for_external_side_effects(self):
        policy = PolicyEngine({"allowed_roots": ["/tmp"], "confirm_risky": True})
        with self.assertRaises(PolicyViolation):
            policy.authorize("gmail_send", {}, confirmed=False)
        policy.authorize("gmail_send", {}, confirmed=True)
        policy.authorize("gmail_draft", {}, confirmed=False)

    def test_policy_rejects_paths_outside_scope(self):
        policy = PolicyEngine({"allowed_roots": ["/tmp"]})
        with self.assertRaises(PolicyViolation):
            policy.validate_paths(["/etc/passwd"])

    def test_planner_validates_capability_names(self):
        policy = PolicyEngine({"allowed_roots": ["/tmp"]})
        planner = Planner({"list_files": lambda _: None}, policy)
        plan = planner.from_actions([Action("list_files", {"dir": "/tmp"})])
        self.assertTrue(plan.dry_run)
        with self.assertRaises(ValueError):
            planner.from_actions([Action("missing", {})])

    def test_chat_service_keeps_sessions_isolated(self):
        class FakeManager:
            def choose(self, task):
                return None

        class FakeAgent:
            lang = "auto"
            model_manager = FakeManager()

            @staticmethod
            def parse_prompt(text):
                return {"action": "ask", "complexity": 1}

            @staticmethod
            def decide_and_run(task):
                return {"model": None, "result": {"text": task["prompt"]}}

        service = ChatService(FakeAgent())
        service.handle("uno", "a")
        service.handle("dos", "b")
        self.assertEqual([item["text"] for item in service.history("a")], ["uno", "uno"])
        self.assertEqual([item["text"] for item in service.history("b")], ["dos", "dos"])

    def test_agent_plan_request_is_validated_before_execution(self):
        from ada.application.agent import Agent

        agent = Agent({"db_path": ":memory:", "allowed_roots": ["/tmp"], "local_runtime": {"auto_start": False}})
        plan = agent.plan_request("listame los archivos")
        self.assertTrue(plan.plan_id)

    def test_capability_catalog_exposes_contracts(self):
        catalog = capability_catalog()
        self.assertIn("filesystem", catalog)
        self.assertIn("argument_schema", catalog["filesystem"])
        self.assertTrue(catalog["filesystem"]["requires_confirmation"])
        self.assertEqual(catalog["gmail_draft"]["risk_level"], "medium")
        self.assertEqual(catalog["gmail_draft"]["permissions"], ["gmail.compose"])
        self.assertTrue(catalog["mcp"]["requires_confirmation"])
        self.assertEqual(catalog["mcp"]["permissions"], ["mcp.execute"])
        self.assertFalse(catalog["gmail_draft"]["requires_confirmation"])
        self.assertEqual(catalog["gmail_send"]["permissions"], ["gmail.send"])


if __name__ == "__main__":
    unittest.main()
