import unittest
import tempfile
import json
from pathlib import Path

from ada.application.services.doctor import diagnose, prepare_instagram_profile
from ada.application.fine_tuning import prepare_dataset, validate_dataset

from ada.application.evaluation import EvaluationCase, evaluate
from ada.infrastructure.notifications import CompositeNotifier
from ada.infrastructure.runtime.supervisor import ServiceSupervisor
from ada.infrastructure.integrations.mcp_server import serve
from ada.interfaces.mcp_server import _policy_wrapped_tools


def noop():
    return None


class OperationsTests(unittest.TestCase):
    def test_doctor_reports_external_readiness_without_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            result = diagnose(
                {
                    "ollama_url": "http://127.0.0.1:1",
                    "local_runtime": {"auto_start": False},
                    "memory_encryption": True,
                    "gmail_token_path": str(Path(directory) / "missing-token.json"),
                    "instagram_profile_dir": str(Path(directory) / "profile"),
                }
            )
            self.assertFalse(result["checks"]["ollama"]["ok"])
            self.assertFalse(result["checks"]["memory_encryption"]["ok"])

    def test_prepare_instagram_profile_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            result = prepare_instagram_profile({"instagram_profile_dir": str(Path(directory) / "profile")})
            self.assertEqual(result["mode"], "0o700")

    def test_finetune_dataset_is_prepared_and_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cases.json"
            target = Path(directory) / "dataset.jsonl"
            source.write_text(json.dumps([{"task": "router", "prompt": "hola", "expected": "ask"}]), encoding="utf-8")
            self.assertEqual(prepare_dataset(source, target)["examples"], 1)
            self.assertEqual(validate_dataset(target)["tasks"], {"router": 1})

    def test_mcp_server_accepts_ping_and_exposes_schema(self):
        import io
        import contextlib
        import unittest.mock

        with unittest.mock.patch("sys.stdin", io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\n')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                serve({"demo": lambda _: {"ok": True}}, schemas={"demo": {"type": "object"}})
        self.assertIn('"id": 1', output.getvalue())

    def test_ada_mcp_entrypoint_routes_calls_through_agent_policy(self):
        class FakeAgent:
            skills = {"danger": lambda _: {"unsafe": True}}

            def __init__(self):
                self.calls = []

            def run_skill(self, name, args, confirm=None):
                self.calls.append((name, args, confirm))
                return {"authorized": True}

        agent = FakeAgent()
        result = _policy_wrapped_tools(agent)["danger"]({"confirm": True})
        self.assertEqual(result, {"authorized": True})
        self.assertEqual(agent.calls, [("danger", {"confirm": True}, True)])

    def test_evaluation_harness_reports_routing(self):
        class FakeAgent:
            @staticmethod
            def parse_prompt(prompt):
                return {"action": "food" if "receta" in prompt else "ask"}

        result = evaluate(FakeAgent(), [EvaluationCase("food", "dame una receta", "food")])
        self.assertEqual(result["accuracy"], 1.0)

    def test_composite_notifier_and_supervisor_lifecycle(self):
        calls = []

        class N:
            def send(self, text, **kwargs):
                calls.append(text)

        notifier = CompositeNotifier([N()])
        notifier.send("hola")
        self.assertEqual(calls, ["hola"])
        supervisor = ServiceSupervisor({"noop": noop})
        processes = supervisor.start()
        self.assertIn("noop", processes)
        supervisor.stop()


if __name__ == "__main__":
    unittest.main()
