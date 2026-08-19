"""Small deterministic regression harness for routing and capabilities."""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class EvaluationCase:
    name: str
    prompt: str
    expected_action: str


def evaluate(agent, cases: List[EvaluationCase]) -> Dict[str, Any]:
    results = []
    for case in cases:
        actual = agent.parse_prompt(case.prompt).get('action')
        results.append({'name': case.name, 'expected': case.expected_action, 'actual': actual,
                        'passed': actual == case.expected_action})
    passed = sum(1 for item in results if item['passed'])
    return {'passed': passed, 'total': len(results), 'accuracy': passed / len(results) if results else 1.0, 'results': results}
