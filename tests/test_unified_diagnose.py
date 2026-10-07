"""Unified diagnose orchestration and CLI front-door tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from minefield.mcp_server import call_tool
from minefield.registry import load_registry
from minefield.unified import diagnose_environment

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = load_registry()


class UnifiedDiagnosisTests(unittest.TestCase):
    def test_file_and_symptom_signals_are_fused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "start.sh"
            path.write_text(
                "sglang serve model --speculative-algorithm DFLASH "
                "--speculative-num-draft-tokens 2\n",
                encoding="utf-8",
            )
            report = diagnose_environment(
                REGISTRY,
                "dflash draft budget 2 never comes up",
                paths=[str(path)],
                limit=10,
            )
        self.assertEqual(report["registry_traps_considered"], 161)
        self.assertIn("161", report["file_scan"]["traps"])
        row = next(item for item in report["candidate_traps"] if item["trap_id"] == "161")
        kinds = {signal["kind"] for signal in row["signals"]}
        self.assertIn("file_scan", kinds)
        self.assertIn(row["evidence_level"], {"file_scan_lead", "multi_signal_lead"})

    def test_no_evidence_still_reports_full_considered_scope(self):
        report = diagnose_environment(REGISTRY, "how do I bake bread")
        self.assertEqual(report["registry_traps_considered"], 161)
        self.assertEqual(report["candidate_traps"], [])
        self.assertGreaterEqual(report["automatic_coverage"]["any_automated_check"], 93)


class UnifiedMcpTests(unittest.TestCase):
    def test_mcp_unified_tool_respects_roots_and_fuses_file_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "start.sh"
            path.write_text(
                "sglang serve model --speculative-algorithm DFLASH "
                "--speculative-num-draft-tokens 2\n",
                encoding="utf-8",
            )
            report = call_tool(
                "diagnose_environment",
                {"symptom": "dflash budget 2 startup failure", "paths": [str(path)]},
                REGISTRY,
                allowed_roots=[str(root)],
            )
        self.assertEqual(report["kind"], "unified_diagnosis")
        self.assertIn("161", report["file_scan"]["traps"])


class UnifiedCliTests(unittest.TestCase):
    def test_diagnose_is_scriptable_json_front_door(self):
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        result = subprocess.run(
            [
                sys.executable, "-m", "minefield", "diagnose",
                "streaming", "shows", "blank", "replies", "--json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "unified_diagnosis")
        self.assertEqual(payload["registry_traps_considered"], 161)
        self.assertIn("23", [item["trap_id"] for item in payload["candidate_traps"]])


if __name__ == "__main__":
    unittest.main()
