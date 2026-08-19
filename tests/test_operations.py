import unittest

from src.ada.application.evaluation import EvaluationCase, evaluate
from src.ada.infrastructure.notifications import CompositeNotifier
from src.ada.infrastructure.runtime.supervisor import ServiceSupervisor


def noop():
    return None


class OperationsTests(unittest.TestCase):
    def test_evaluation_harness_reports_routing(self):
        class FakeAgent:
            @staticmethod
            def parse_prompt(prompt):
                return {'action': 'food' if 'receta' in prompt else 'ask'}
        result = evaluate(FakeAgent(), [EvaluationCase('food', 'dame una receta', 'food')])
        self.assertEqual(result['accuracy'], 1.0)

    def test_composite_notifier_and_supervisor_lifecycle(self):
        calls = []
        class N:
            def send(self, text, **kwargs):
                calls.append(text)
        notifier = CompositeNotifier([N()])
        notifier.send('hola')
        self.assertEqual(calls, ['hola'])
        supervisor = ServiceSupervisor({'noop': noop})
        processes = supervisor.start()
        self.assertIn('noop', processes)
        supervisor.stop()


if __name__ == '__main__':
    unittest.main()
