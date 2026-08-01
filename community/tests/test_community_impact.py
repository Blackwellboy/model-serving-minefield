#!/usr/bin/env python3
"""Positive and negative tests for community impact ledger."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integrity"))
sys.path.insert(0, str(ROOT / "community"))

import community_impact_integrity as cii  # noqa: E402
import generate_impact as gen  # noqa: E402


def base_record(**over):
    r = {
        "impact_id": "impact-20260801-example-record",
        "date": "2026-08-01",
        "type": "ADOPTION",
        "person_or_project": "@someone / project",
        "contributors": ["@someone"],
        "maintainers": ["@Blackwellboy"],
        "credit_statement": "Contributor @someone reported; maintainer filed.",
        "public_source": "https://github.com/Blackwellboy/model-serving-minefield/issues/1",
        "summary": "Example adoption without success language.",
        "minefield_role": "catalog",
        "related_issue": "https://github.com/Blackwellboy/model-serving-minefield/issues/1",
        "related_traps": [],
        "evidence_status": "PUBLIC_PRIMARY",
        "permission_to_publish": "public_issue",
        "permission_to_quote": "public_issue",
        "wording_guardrail": "no inflated metrics",
        "follow_up_state": "closed_completed",
        "source_state": "CLOSED_COMPLETED",
        "source_state_reason": "example closed",
        "last_verified": "2026-08-01",
    }
    r.update(over)
    return r


class CommunityImpactTests(unittest.TestCase):
    def test_schema_top_level_array(self):
        schema = json.loads((ROOT / "community" / "impact.schema.json").read_text())
        self.assertEqual(schema["type"], "array")
        self.assertIn("items", schema)
        self.assertEqual(schema["items"]["type"], "object")
        self.assertFalse(schema["items"].get("additionalProperties", True))

    def test_real_ledger_passes(self):
        data = json.loads((ROOT / "community" / "impact.json").read_text())
        fails = cii.validate_records(data)
        self.assertEqual(fails, [], fails)

    def test_duplicate_ids(self):
        a = base_record()
        b = base_record()
        fails = cii.validate_records([a, b])
        self.assertTrue(any("duplicate" in f for f in fails), fails)

    def test_missing_contributor_attribution(self):
        r = base_record(
            type="CONTRIBUTOR_DISCOVERY",
            contributors=[],
            person_or_project="@Blackwellboy",
            source_state="OPEN",
            follow_up_state="pending",
            source_state_reason="open intake",
        )
        fails = cii.validate_records([r])
        self.assertTrue(
            any("requires contributors" in f for f in fails), fails
        )

    def test_maintainer_only_credit(self):
        r = base_record(
            type="CONTRIBUTOR_DISCOVERY",
            contributors=["@alice"],
            person_or_project="@Blackwellboy",
            maintainers=["@Blackwellboy"],
            credit_statement="Maintainer only narrative",
            source_state="OPEN",
            follow_up_state="pending",
            source_state_reason="open",
        )
        fails = cii.validate_records([r])
        self.assertTrue(
            any("maintainer only" in f or "credit a contributor" in f for f in fails),
            fails,
        )

    def test_missing_guardrail(self):
        r = base_record(
            type="CONTRIBUTOR_DISCOVERY",
            contributors=["@alice"],
            person_or_project="@alice",
            wording_guardrail=None,
            source_state="OPEN",
            follow_up_state="pending",
            source_state_reason="open",
        )
        fails = cii.validate_records([r])
        self.assertTrue(any("guardrail" in f for f in fails), fails)

    def test_invalid_type(self):
        r = base_record(type="NOT_A_TYPE")
        fails = cii.validate_records([r])
        self.assertTrue(any("bad type" in f for f in fails), fails)

    def test_downstream_reference_accepted(self):
        r = base_record(
            type="DOWNSTREAM_REFERENCE",
            impact_id="impact-20260801-downstream-ref",
            follow_up_state="none",
            source_state="EXTERNAL_STATIC",
            source_state_reason="static external doc",
        )
        fails = cii.validate_records([r])
        self.assertEqual(fails, [], fails)

    def test_contradictory_source_state_issue19(self):
        r = base_record(
            type="CONTRIBUTOR_DISCOVERY",
            contributors=["@scottleimroth"],
            person_or_project="@scottleimroth",
            related_issue="https://github.com/Blackwellboy/model-serving-minefield/issues/19",
            source_state="CLOSED_COMPLETED",
            follow_up_state="closed_completed",
            source_state_reason="wrongly closed",
        )
        fails = cii.validate_records([r])
        self.assertTrue(any("issue #19" in f for f in fails), fails)

    def test_issue18_must_not_be_open(self):
        r = base_record(
            related_issue="https://github.com/Blackwellboy/model-serving-minefield/issues/18",
            source_state="OPEN",
            follow_up_state="pending",
            source_state_reason="wrong",
        )
        fails = cii.validate_records([r])
        self.assertTrue(any("issue #18" in f for f in fails), fails)

    def test_unsupported_success_language(self):
        r = base_record(summary="This saved hours for everyone")
        fails = cii.validate_records([r])
        self.assertTrue(any("success language" in f for f in fails), fails)

    def test_missing_public_source(self):
        r = base_record(public_source="not-a-url")
        fails = cii.validate_records([r])
        self.assertTrue(any("public_source" in f for f in fails), fails)

    def test_generator_deterministic_and_check(self):
        # render twice must match
        data = json.loads((ROOT / "community" / "impact.json").read_text())
        t1 = gen.render(sorted(data, key=lambda r: (r["date"], r["impact_id"])))
        t2 = gen.render(sorted(data, key=lambda r: (r["date"], r["impact_id"])))
        self.assertEqual(t1, t2)
        self.assertIn("@scottleimroth", t1)
        self.assertNotIn("Generated at", t1)
        # --check against real file after ensure written
        rc = subprocess.run(
            [sys.executable, str(ROOT / "community" / "generate_impact.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(rc.returncode, 0, rc.stderr)
        rc = subprocess.run(
            [sys.executable, str(ROOT / "community" / "generate_impact.py"), "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(rc.returncode, 0, rc.stderr)
        # stale check
        md = ROOT / "community" / "COMMUNITY_IMPACT.md"
        original = md.read_text()
        try:
            md.write_text(original + "\n# tamper\n")
            rc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "community" / "generate_impact.py"),
                    "--check",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(rc.returncode, 1)
        finally:
            md.write_text(original)

    def test_no_hardcoded_scottleimroth_in_checker(self):
        src = (ROOT / "integrity" / "community_impact_integrity.py").read_text()
        # generic attribution: name must not appear as special-case string
        self.assertNotIn("scottleimroth", src.lower())

    def test_issue19_env_control_follow_up_state_accepted(self):
        data = json.loads((ROOT / "community" / "impact.json").read_text())
        rec = next(
            r
            for r in data
            if r.get("impact_id")
            == "impact-20260801-issue19-unvalidated-config-surface"
        )
        self.assertEqual(
            rec["follow_up_state"], "env_control_complete_engine_control_pending"
        )
        fails = cii.validate_records(data)
        self.assertEqual(fails, [], fails)

    def test_issue19_generated_output_env_complete_engine_pending(self):
        data = json.loads((ROOT / "community" / "impact.json").read_text())
        text = gen.render(sorted(data, key=lambda r: (r["date"], r["impact_id"])))
        self.assertIn("env_control_complete_engine_control_pending", text)
        self.assertIn("--fail-on-environ-validation", text)
        # env complete language present; engine still pending
        low = text.lower()
        self.assertTrue(
            "environment-level" in low
            or "env validation control complete" in low
            or "env_control_complete" in low
        )
        self.assertIn("engine-level backend-selection control", low)
        self.assertIn("remains pending", low)
        self.assertIn("engine-selection control pending", low)
        self.assertIn("not a general cutlass all-clear", low)
        self.assertIn("@scottleimroth", text)
        self.assertIn("source_state", low) or self.assertIn("OPEN", text)
        # source_state OPEN for issue 19 record body
        self.assertRegex(
            text,
            r"impact-20260801-issue19-unvalidated-config-surface[\s\S]*?\*\*Source state:\*\* OPEN",
        )
        # no numbered trap assignment language that implies trap ID assigned
        issue19_section = text.split("### impact-20260801-issue19-unvalidated-config-surface", 1)[
            -1
        ].split("### ", 1)[0]
        self.assertIn("no numbered trap assigned", issue19_section.lower())
        self.assertNotRegex(issue19_section, r"trap\s+#?\d{2,}\s+assigned")

    def test_issue19_contributor_credit_cannot_be_replaced_by_maintainer(self):
        r = base_record(
            impact_id="impact-20260801-issue19-unvalidated-config-surface",
            type="CONTRIBUTOR_DISCOVERY",
            contributors=["@scottleimroth"],
            person_or_project="@Blackwellboy",
            maintainers=["@Blackwellboy"],
            credit_statement="Maintainer @Blackwellboy discovered and owns this finding",
            related_issue="https://github.com/Blackwellboy/model-serving-minefield/issues/19",
            wording_guardrail="MEASURED_ON_THIS_BUILD",
            follow_up_state="env_control_complete_engine_control_pending",
            source_state="OPEN",
            source_state_reason="open intake",
        )
        fails = cii.validate_records([r])
        self.assertTrue(
            any(
                "credit a contributor" in f
                or "maintainer" in f.lower()
                or "person_or_project" in f
                for f in fails
            ),
            fails,
        )

    def test_issue19_source_state_must_remain_open(self):
        r = base_record(
            impact_id="impact-20260801-issue19-unvalidated-config-surface",
            type="CONTRIBUTOR_DISCOVERY",
            contributors=["@alice"],
            person_or_project="@alice",
            related_issue="https://github.com/Blackwellboy/model-serving-minefield/issues/19",
            wording_guardrail="MEASURED_ON_THIS_BUILD; engine pending",
            follow_up_state="env_control_complete_engine_control_pending",
            source_state="CLOSED_COMPLETED",
            source_state_reason="wrongly closed after env control",
        )
        fails = cii.validate_records([r])
        self.assertTrue(any("issue #19" in f for f in fails), fails)


if __name__ == "__main__":
    unittest.main()
