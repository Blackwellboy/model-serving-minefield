#!/usr/bin/env python3
"""Unit tests for offline benchmark attribution preflight."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "checks" / "benchmark_attribution_preflight.py"
DOCS = ROOT / "docs"


def load_check():
    spec = importlib.util.spec_from_file_location("benchmark_attribution_preflight", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BenchmarkAttributionPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_check()

    def _example(self):
        return json.loads((DOCS / "benchmark-attribution.example.json").read_text(encoding="utf-8"))

    def _bad(self):
        return json.loads((DOCS / "benchmark-attribution.bad-example.json").read_text(encoding="utf-8"))

    def test_clean_transport_example_allows_transport(self):
        report = self.m.evaluate_pair(self._example())
        self.assertEqual(report["max_defensible_claim"], "TRANSPORT")
        self.assertEqual(self.m.gate_intended(report), self.m.OK)

    def test_model_intended_but_transport_differs_is_composite(self):
        report = self.m.evaluate_pair(self._bad())
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertEqual(self.m.gate_intended(report), self.m.BLOCKING)

    def test_transport_without_path_proof_is_composite(self):
        doc = self._example()
        doc["arm_a"]["transport"]["path_proof"] = "ABSENT"
        doc["arm_b"]["transport"]["path_proof"] = "ABSENT"
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertEqual(report["path_proof_status"], "ABSENT")

    def test_link_up_only_free_text_is_not_path_proof(self):
        doc = self._example()
        doc["arm_a"]["transport"]["path_proof"] = "link UP at 1 Gb/s"
        doc["arm_b"]["transport"]["path_proof"] = "link UP at 1 Gb/s"
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["path_proof_status"], "INSUFFICIENT")
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertEqual(self.m.gate_intended(report), self.m.BLOCKING)

    def test_route_and_counter_free_text_can_be_path_proof(self):
        doc = self._example()
        proof = "route to peer uses interface eth0; TX/RX counters move during burst"
        doc["arm_a"]["transport"]["path_proof"] = proof
        doc["arm_b"]["transport"]["path_proof"] = proof
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["path_proof_status"], "PRESENT")
        self.assertEqual(report["max_defensible_claim"], "TRANSPORT")

    def test_concurrency_compares_exactly_not_with_token_tolerance(self):
        doc = self._example()
        doc["arm_a"]["serving_engine"]["concurrency"] = 1
        doc["arm_b"]["serving_engine"]["concurrency"] = 2
        report = self.m.evaluate_pair(doc)
        self.assertIn("SERVING_ENGINE", report["changed_dimensions"])
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertEqual(self.m.gate_intended(report), self.m.BLOCKING)

    def test_serving_missing_isl_cannot_claim_serving_engine(self):
        doc = self._example()
        doc["intended_changed_layer"] = "SERVING_ENGINE"
        doc["arm_a"]["transport"] = deepcopy(doc["arm_b"]["transport"])
        doc["arm_a"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=old"
        doc["arm_b"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=new"
        doc["arm_a"]["serving_engine"]["actual_isl"] = None
        doc["arm_b"]["serving_engine"]["actual_isl"] = None
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")

    def test_serving_missing_concurrency_cannot_claim_serving_engine(self):
        doc = self._example()
        doc["intended_changed_layer"] = "SERVING_ENGINE"
        doc["arm_a"]["transport"] = deepcopy(doc["arm_b"]["transport"])
        doc["arm_a"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=old"
        doc["arm_b"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=new"
        doc["arm_a"]["serving_engine"]["concurrency"] = None
        doc["arm_b"]["serving_engine"]["concurrency"] = None
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertEqual(self.m.gate_intended(report), self.m.BLOCKING)

    def test_gpudirect_from_cuda_managed_rejected(self):
        report = self.m.evaluate_pair(self._bad())
        self.assertTrue(report["gpudirect_inference_rejected"])

    def test_absent_correctness_gate_limits_claim(self):
        doc = self._example()
        doc["arm_a"]["model"]["correctness_gate"] = "ABSENT"
        doc["arm_b"]["model"]["correctness_gate"] = "ABSENT"
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertEqual(report["correctness_gate_status"], "ABSENT")

    def test_transport_intended_but_endpoint_identity_differs_is_composite(self):
        doc = self._example()
        doc["arm_a"]["serving_engine"]["endpoint_or_host_identity"] = "peer-a"
        doc["arm_b"]["serving_engine"]["endpoint_or_host_identity"] = "peer-b"
        report = self.m.evaluate_pair(doc)
        self.assertIn("SERVING_ENGINE", report["changed_dimensions"])
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")

    def test_missing_arms_are_blocking_shape_failure(self):
        report = self.m.evaluate_pair({"intended_changed_layer": "TRANSPORT"})
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(self.m.gate_intended(report), self.m.BLOCKING)

    def test_schema_examples_are_objects(self):
        for name in (
            "benchmark-attribution.schema.json",
            "benchmark-attribution.example.json",
            "benchmark-attribution.bad-example.json",
        ):
            doc = json.loads((DOCS / name).read_text(encoding="utf-8"))
            self.assertIsInstance(doc, dict)


if __name__ == "__main__":
    unittest.main()
