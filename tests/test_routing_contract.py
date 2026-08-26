import json
import unittest
from pathlib import Path


class RoutingContractTests(unittest.TestCase):
    def test_routing_cases_have_verifiable_contracts(self):
        cases = json.loads((Path(__file__).with_name("routing_cases.json")).read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 8)
        for case in cases:
            self.assertTrue(case["id"])
            self.assertTrue(case["prompt"])
            self.assertTrue(case["category"])
            self.assertTrue(case.get("must_contain") or case.get("must_match"))


if __name__ == "__main__":
    unittest.main()
