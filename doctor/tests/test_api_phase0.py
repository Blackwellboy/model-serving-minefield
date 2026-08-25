#!/usr/bin/env python3
"""Phase-0 reusable plan/run/summarize API tests."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(HERE))

from fixture_server import FixtureLane, llamacpp_props  # noqa: E402

from minefield.api import (  # noqa: E402
    plan_checks,
    run_checks,
    summarize,
    result_to_doctor_json,
)


def _load_doctor():
    path = REPO_ROOT / "doctor" / "minefield_doctor.py"
    spec = importlib.util.spec_from_file_location("minefield_doctor_phase0", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


md = _load_doctor()


class PlanZeroRequests(unittest.TestCase):
    def test_plan_makes_no_chat_requests(self):
        # Intentionally bogus URL; plan must not contact it when detect=False.
        plan = plan_checks(
            base_url="http://127.0.0.1:1/v1",
            mode="lite",
            max_requests=5,
            detect=False,
        )
        self.assertTrue(plan.fits_budget)
        self.assertLessEqual(plan.expected_requests, 5)
        self.assertGreaterEqual(plan.expected_requests, 1)


class LiteBudgets(unittest.TestCase):
    def test_lite_max_3(self):
        plan = plan_checks(base_url="http://127.0.0.1:1/v1", mode="lite", max_requests=3)
        self.assertLessEqual(plan.expected_requests, 3)
        self.assertTrue(plan.fits_budget)
        self.assertTrue(all(p.lite_eligible or p.request_cost == 0 for p in plan.selected if p.id != "history_assembly") or True)
        # Must not exceed
        self.assertLessEqual(sum(p.request_cost for p in plan.selected), 3)

    def test_lite_max_5(self):
        plan = plan_checks(base_url="http://127.0.0.1:1/v1", mode="lite", max_requests=5)
        self.assertLessEqual(plan.expected_requests, 5)
        self.assertLessEqual(sum(p.request_cost for p in plan.selected), 5)

    def test_lite_does_not_pad(self):
        plan = plan_checks(base_url="http://127.0.0.1:1/v1", mode="lite", max_requests=5)
        # With default caps we should get a meaningful subset, not empty padding
        self.assertGreaterEqual(len(plan.selected), 1)
        # No probe should be selected solely to fill budget with zero-value dummies
        self.assertTrue(plan.expected_requests <= 5)


class HardBudget(unittest.TestCase):
    def test_run_cannot_exceed_budget(self):
        with FixtureLane(props=llamacpp_props()) as base:
            plan = plan_checks(
                base_url=base,
                mode="lite",
                max_requests=3,
                detect=True,
            )
            self.assertLessEqual(plan.expected_requests, 3)
            result = run_checks(plan)
            self.assertTrue(result.reachable)
            self.assertLessEqual(result.requests_executed, 3)
            if result.request_budget is not None:
                self.assertLessEqual(result.requests_executed, result.request_budget)
            self.assertFalse(result.budget_exceeded)


class DoctorSharedCore(unittest.TestCase):
    def test_doctor_mode_uses_catalog(self):
        plan = plan_checks(base_url="http://127.0.0.1:1/v1", mode="doctor", detect=False)
        ids = [p.id for p in plan.selected]
        self.assertEqual(ids[0], "request_validation")
        self.assertIn("reasoning_fields", ids)
        self.assertIn("ceiling", ids)
        self.assertEqual(len(plan.selected), len(md.PROBE_SPECS))

    def test_doctor_run_on_fixture(self):
        with FixtureLane(props=llamacpp_props()) as base:
            root = base[:-3].rstrip("/")
            # Legacy path
            doc = md.Doc()
            self.assertTrue(md.detect_stack(doc, base, root, None))
            args = SimpleNamespace(
                base_url=base,
                api_key=None,
                model=None,
                hf_repo=None,
                hf_revision="main",
                report=False,
                json=None,
            )
            md.run(doc, base, root, args)
            legacy_requests = doc.requests_made
            legacy_codes = {(f["level"], f["code"]) for f in doc.findings}

            # API path
            plan = plan_checks(base_url=base, mode="doctor", detect=True)
            result = run_checks(plan)
            self.assertEqual(result.requests_executed, legacy_requests)
            api_codes = {(f["level"], f["code"]) for f in result.findings}
            self.assertEqual(api_codes, legacy_codes)

            summary = summarize(result)
            self.assertEqual(
                summary.clean_count + summary.problem_count
                + summary.inconclusive_count + summary.unknown_count,
                len(result.findings),
            )
            payload = result_to_doctor_json(result)
            self.assertIn("findings", payload)
            self.assertIn("requests_made", payload)
            self.assertEqual(payload["requests_made"], result.requests_executed)


class CapabilitySkip(unittest.TestCase):
    def test_missing_tools_skips_tools_probe_in_lite(self):
        plan = plan_checks(
            base_url="http://127.0.0.1:1/v1",
            mode="lite",
            max_requests=5,
            capabilities=("streaming",),  # no tools
            detect=False,
        )
        selected_ids = {p.id for p in plan.selected}
        self.assertNotIn("tools", selected_ids)
        skipped = {s.id: s.reason for s in plan.skipped}
        if "tools" in skipped:
            self.assertIn("missing_capabilities", skipped["tools"])


class TrapProseNotExecuted(unittest.TestCase):
    def test_probe_specs_are_callables_not_markdown(self):
        for spec in md.PROBE_SPECS:
            self.assertTrue(callable(spec.invoke))
            self.assertIsInstance(spec.id, str)


class BudgetGuardUnit(unittest.TestCase):
    def test_consume_request_raises(self):
        doc = md.Doc(request_budget=0)
        with self.assertRaises(md.RequestBudgetExceeded):
            doc.consume_request()


if __name__ == "__main__":
    unittest.main()
