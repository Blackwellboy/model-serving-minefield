"""Trap 135 must remain stack-unrestricted despite Related mentioning llama.cpp."""

from __future__ import annotations

import unittest

from minefield.diagnosis_contract import contract_for_match
from minefield.registry import compile_registry


class Trap135StackApplicabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = compile_registry()
        cls.entry = next(item for item in cls.registry["entries"] if item["id"] == "135")

    def test_generated_serving_stack_unrestricted(self):
        self.assertEqual(self.entry.get("affected_stacks"), [])
        self.assertEqual(self.entry.get("applicability", {}).get("serving_stack"), [])

    def test_non_llama_stacks_do_not_condition_mismatch(self):
        for stack in ("vllm", "sglang", "ollama", "custom-adapter"):
            with self.subTest(stack=stack):
                match = contract_for_match(
                    self.entry,
                    observed_symptom=self.entry["symptom"],
                    symptom_score=5,
                    observed_conditions={"serving_stack": [stack]},
                    direct_probe_support=False,
                    direct_probe_result="not_supplied",
                )
                self.assertNotEqual(
                    match["diagnosis_level"],
                    "CONDITION_MISMATCH",
                    msg=f"stack={stack} mismatched={match.get('mismatched_conditions')}",
                )
                mismatched_fields = [
                    item.split(":", 1)[0]
                    for item in match.get("mismatched_conditions", [])
                ]
                self.assertNotIn("serving_stack", mismatched_fields)


if __name__ == "__main__":
    unittest.main()
