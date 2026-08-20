import unittest
import tempfile
from pathlib import Path

from ada.application.services.doctor import diagnose, prepare_instagram_profile

from ada.application.evaluation import EvaluationCase, evaluate
from ada.infrastructure.notifications import CompositeNotifier
from ada.infrastructure.runtime.supervisor import ServiceSupervisor


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
