#!/usr/bin/env python3
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "checks"))
import concurrency_execution_proof_preflight as chk  # noqa: E402


class ConcurrencyExecutionProofTests(unittest.TestCase):
    def test_example_flags(self):
        doc = json.loads((ROOT / "docs/concurrency-execution-proof.example.json").read_text())
        code, findings, flags = chk.evaluate(doc)
        self.assertEqual(code, chk.BLOCKING)
        self.assertIn("CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF", flags)

    def test_scaling_ok(self):
        doc = json.loads((ROOT / "docs/concurrency-execution-proof.scaling-example.json").read_text())
        code, _, flags = chk.evaluate(doc)
        self.assertEqual(code, chk.OK)
        self.assertEqual(flags, [])

    def test_empty_is_nothing(self):
        code, _, _ = chk.evaluate({"rows": []})
        self.assertEqual(code, chk.NOTHING)

    def test_active_sequences_rise_still_flags(self):
        """Rising accepted/live sequences must not veto the wall/throughput signature."""
        doc = {"rows": [
            {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0, "active_sequences": 1},
            {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.0, "active_sequences": 2},
            {"concurrency": 4, "batch_wall": 8.0, "aggregate_tps": 15.0, "active_sequences": 4},
        ]}
        code, findings, flags = chk.evaluate(doc)
        self.assertEqual(code, chk.BLOCKING)
        self.assertIn("CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF", flags)
        self.assertTrue(any("active_sequences rose" in line for line in findings))

    def test_zero_throughput_is_not_ok(self):
        doc = {"rows": [
            {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 0},
            {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 0},
            {"concurrency": 4, "batch_wall": 8.0, "aggregate_tps": 0},
        ]}
        code, findings, flags = chk.evaluate(doc)
        self.assertNotEqual(code, chk.OK)
        self.assertEqual(code, chk.NOTHING)
        self.assertEqual(flags, [])
        self.assertTrue(any("aggregate_tps<=0" in line for line in findings))

    def test_zero_baseline_with_later_positive_is_not_ok(self):
        doc = {"rows": [
            {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 0},
            {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.0},
        ]}
        code, findings, _flags = chk.evaluate(doc)
        self.assertNotEqual(code, chk.OK)
        self.assertEqual(code, chk.NOTHING)
        self.assertTrue(any("zero baseline" in line for line in findings))

    def test_nan_and_inf_block(self):
        for bad in (float("nan"), float("inf"), -1):
            with self.subTest(bad=bad):
                code, _, _ = chk.evaluate({"rows": [
                    {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0},
                    {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": bad},
                ]})
                self.assertEqual(code, chk.BLOCKING)

    def test_duplicate_disagreeing_rows_block(self):
        code, findings, _ = chk.evaluate({"rows": [
            {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0},
            {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.0},
            {"concurrency": 2, "batch_wall": 9.0, "aggregate_tps": 15.0},
        ]})
        self.assertEqual(code, chk.BLOCKING)
        self.assertTrue(any("duplicate concurrency" in line for line in findings))

    def test_missing_active_sequences_still_flags(self):
        code, _, flags = chk.evaluate({"rows": [
            {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0},
            {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.1},
            {"concurrency": 4, "batch_wall": 8.0, "aggregate_tps": 14.9},
        ]})
        self.assertEqual(code, chk.BLOCKING)
        self.assertIn("CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF", flags)


class Trap135StackApplicabilityTests(unittest.TestCase):
    """Trap 135 must remain stack-unrestricted despite Related mentioning llama.cpp."""

    @classmethod
    def setUpClass(cls):
        from minefield.registry import compile_registry
        from minefield.diagnosis_contract import contract_for_match

        cls.registry = compile_registry()
        cls.entry = next(item for item in cls.registry["entries"] if item["id"] == "135")
        cls.contract_for_match = staticmethod(contract_for_match)

    def test_generated_serving_stack_unrestricted(self):
        self.assertEqual(self.entry.get("affected_stacks"), [])
        self.assertEqual(self.entry.get("applicability", {}).get("serving_stack"), [])

    def test_non_llama_stacks_do_not_condition_mismatch(self):
        for stack in ("vllm", "sglang", "ollama", "custom-adapter"):
            with self.subTest(stack=stack):
                match = self.contract_for_match(
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
