#!/usr/bin/env python3
import json
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


if __name__ == "__main__":
    unittest.main()
