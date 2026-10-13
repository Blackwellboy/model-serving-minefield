"""Regression contract for the zero-network Doctor planning CLI."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from minefield.cli import main


def plan(*argv: str):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
                rc = main(["doctor-plan", *argv])
    return rc, stdout.getvalue(), stderr.getvalue()


class OfflineDoctorPlanTests(unittest.TestCase):
    def test_default_is_bounded_and_not_run(self):
        rc, out, err = plan()
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["kind"], "doctor_plan")
        self.assertEqual(data["execution"], "NOT_RUN")
        self.assertEqual(data["network_calls_made"], 0)
        self.assertEqual(data["generation_requests_made"], 0)
        self.assertEqual(data["chat_request_budget"], 5)
        self.assertLessEqual(data["planned_chat_requests_upper_bound"], 5)
        self.assertFalse(data["model_identity_verified"])
        self.assertFalse(data["capabilities_verified"])
        self.assertGreater(data["selected_probe_count"], 0)
        self.assertEqual(
            data["planned_chat_requests_upper_bound"],
            sum(item["chat_request_cost"] for item in data["selected_probes"]),
        )
        self.assertNotIn("127.0.0.1:0", out)
        self.assertTrue(set(data["planned_trap_ids"]).issubset(
            {str(i).zfill(2) for i in range(1, data["canonical_trap_count"] + 1)}
        ))

    def test_zero_chat_budget_is_not_zero_network_assertion(self):
        rc, out, err = plan("--max-requests", "0")
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["planned_chat_requests_upper_bound"], 0)
        self.assertTrue(all(p["chat_request_cost"] == 0 for p in data["selected_probes"]))
        self.assertTrue(any("does not mean zero HTTP" in w for w in data["warnings"]))

    def test_matched_trap_takes_priority_in_lite_mode(self):
        rc, out, err = plan("--preferred-trap", "12", "--max-requests", "1")
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["selected_probes"][0]["id"], "ceiling")
        self.assertIn("12", data["planned_trap_ids"])
        self.assertLessEqual(data["planned_chat_requests_upper_bound"], 1)

    def test_doctor_mode_is_explicit_and_can_be_capped(self):
        rc, out, err = plan("--mode", "doctor", "--max-requests", "4")
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["chat_request_budget"], 4)
        self.assertLessEqual(data["planned_chat_requests_upper_bound"], 4)
        self.assertGreater(data["skipped_probe_count"], 0)
        self.assertLessEqual(data["planned_trap_count"], data["registered_doctor_traps"])

    def test_hf_and_capability_are_unverified_inputs(self):
        rc, out, err = plan(
            "--hf-repo", "example/multimodal", "--capability", "multimodal",
            "--model", "example/model", "--max-requests", "0",
        )
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertFalse(data["model_identity_verified"])
        self.assertFalse(data["capabilities_verified"])
        self.assertTrue(any("Hugging Face" in w for w in data["warnings"]))

    def test_invalid_budget_and_trap_fail_closed(self):
        for args in (("--max-requests", "-1"), ("--preferred-trap", "999")):
            with self.subTest(args=args):
                rc, _out, err = plan(*args)
                self.assertEqual(rc, 2)
                self.assertTrue(err)

    def test_text_mode_never_says_clean(self):
        rc, out, err = plan("--text", "--max-requests", "2")
        self.assertEqual(rc, 0, err)
        self.assertIn("NOT RUN", out)
        self.assertIn("No network calls", out)
        self.assertNotIn("CHECKED AND CLEAN", out)


if __name__ == "__main__":
    unittest.main()
