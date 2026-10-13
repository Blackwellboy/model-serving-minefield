"""Truthfulness regressions when unified diagnosis fuses live Doctor findings."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from minefield.api import TargetInfo
from minefield.registry import load_registry
from minefield.unified import diagnose_environment


REGISTRY = load_registry()


def diagnostic(findings, symptom="how do I bake bread"):
    target = TargetInfo(
        base_url="http://example.invalid/v1",
        root_url="http://example.invalid",
        stack="vllm",
        model="fixture-model",
        reachable=True,
        capabilities=("streaming",),
    )
    with (
        patch("minefield.unified.detect_target", return_value=target),
        patch("minefield.unified.plan_checks", return_value=SimpleNamespace(selected=())),
        patch("minefield.unified.run_checks", return_value=object()),
        patch("minefield.unified.result_to_doctor_json", return_value={"findings": findings}),
    ):
        return diagnose_environment(
            REGISTRY,
            symptom,
            base_url="http://example.invalid/v1",
            limit=100,
        )


def finding(level, trap, code):
    return {"level": level, "traps": [trap], "code": code, "title": code}


class LiveEvidenceTruthTests(unittest.TestCase):
    def test_problem_overrides_clean_and_unknown_only_is_not_a_lead(self):
        data = diagnostic([
            finding("OK", "23", "PASS_FIRST"),
            finding("PROBLEM", "23", "FAIL_SECOND"),
            finding("INCONCLUSIVE", "59", "INCONCLUSIVE_ONLY"),
            finding("UNKNOWN", "60", "UNAVAILABLE_ONLY"),
        ])
        self.assertNotIn("23", data["live_checked_clean_traps"])
        self.assertIn("60", data["live_could_not_check_traps"])
        rows = {row["trap_id"]: row for row in data["candidate_traps"]}
        self.assertNotIn("60", rows)
        self.assertEqual(rows["23"]["evidence_level"], "live_probe_problem")
        self.assertEqual(rows["59"]["evidence_level"], "live_probe_inconclusive")
        self.assertTrue(any("Conflicting live verdicts" in w for w in data["warnings"]))

    def test_unknown_overrides_clean_without_becoming_positive_evidence(self):
        data = diagnostic([
            finding("UNKNOWN", "23", "NOT_AVAILABLE"),
            finding("OK", "23", "PASS_FROM_OTHER_PROBE"),
        ])
        self.assertNotIn("23", data["live_checked_clean_traps"])
        self.assertIn("23", data["live_could_not_check_traps"])
        self.assertNotIn("23", [row["trap_id"] for row in data["candidate_traps"]])

    def test_symptom_plus_unknown_remains_only_a_symptom_lead(self):
        data = diagnostic([
            finding("UNKNOWN", "23", "NOT_AVAILABLE"),
        ], symptom="streaming shows blank replies")
        row = next(row for row in data["candidate_traps"] if row["trap_id"] == "23")
        self.assertEqual(row["evidence_level"], "symptom_lead")
        self.assertIn("23", data["live_could_not_check_traps"])


if __name__ == "__main__":
    unittest.main()
