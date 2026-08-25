#!/usr/bin/env python3
"""Unit tests for offline benchmark attribution preflight.

    python3 checks/tests/test_benchmark_attribution_preflight.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
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
        """Cross-session footgun: path changed AND remote host changed."""
        doc = self._example()
        doc["intended_changed_layer"] = "TRANSPORT"
        doc["arm_a"]["serving_engine"]["endpoint_or_host_identity"] = "spark-peer-wifi-era"
        doc["arm_b"]["serving_engine"]["endpoint_or_host_identity"] = "spark-peer-wired-era"
        # Even with identical engine_build, a host move blocks pure TRANSPORT.
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")
        self.assertIn("SERVING_ENGINE", report["changed_dimensions"])
        self.assertEqual(self.m.gate_intended(report), self.m.BLOCKING)

    def test_transport_intended_with_endpoint_and_revision_differs_is_composite(self):
        doc = self._example()
        doc["intended_changed_layer"] = "TRANSPORT"
        doc["arm_a"]["serving_engine"]["endpoint_or_host_identity"] = "spark-peer-wifi-era"
        doc["arm_b"]["serving_engine"]["endpoint_or_host_identity"] = "spark-peer-wired-era"
        doc["arm_a"]["serving_engine"]["engine_build"] = (
            "flashrdma-portable@ae03d59a04015d9c73ee6b029520aad9026484e5"
        )
        doc["arm_b"]["serving_engine"]["engine_build"] = (
            "flashrdma-portable@1e952ace4be94f90b88b850188e99f0493036424"
        )
        doc["arm_a"]["transport"]["path_class"] = "WIFI_PORTABLE"
        doc["arm_b"]["transport"]["path_class"] = "WIRED_ETHERNET_FLASH_PORTABLE"
        report = self.m.evaluate_pair(doc)
        self.assertEqual(report["max_defensible_claim"], "END_TO_END_COMPOSITE_ONLY")

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
