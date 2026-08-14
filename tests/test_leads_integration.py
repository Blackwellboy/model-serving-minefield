import json
import unittest
from pathlib import Path

from minefield.leads import load_leads, search_leads
from minefield.matching import diagnose

ROOT = Path(__file__).resolve().parents[1]


class UnverifiedLeadIntegrationTests(unittest.TestCase):
    def test_packaged_catalogue_matches_repository_authority(self):
        source = json.loads((ROOT / "leads" / "LEADS.json").read_text(encoding="utf-8"))
        packaged = load_leads()
        self.assertEqual(source, packaged)

    def test_specific_admission_symptom_routes_to_l003(self):
        matches = search_leads("request waits before prefill below displayed context capacity")
        self.assertTrue(matches)
        self.assertEqual("L003", matches[0]["lead_id"])
        self.assertFalse(matches[0]["canonical"])
        self.assertEqual("POSSIBLE_UNVERIFIED_LEAD", matches[0]["lead_match_level"])
        self.assertIn("not a canonical", matches[0]["warning"])

    def test_canonical_miss_can_return_bounded_lead(self):
        registry = {"entries": []}
        result = diagnose(registry, "selected endpoint still benchmarks the old backend")
        self.assertEqual("NOT_DOCUMENTED", result["diagnosis_level"])
        self.assertEqual([], result["matches"])
        self.assertTrue(result["possible_unverified_leads"])
        self.assertEqual("L004", result["possible_unverified_leads"][0]["lead_id"])
        self.assertIn("unverified", result["warning"].lower())

    def test_canonical_hit_keeps_leads_separate(self):
        registry = {"entries": [{
            "id": "91",
            "title": "benchmark path fixture",
            "symptom": "selected endpoint benchmark mismatch",
            "check": "Confirm the actual request destination.",
            "mechanism": "A canonical fixture mechanism.",
            "mitigation": "Fix only after confirmation.",
            "status": "reproduced here",
            "evidence_strength": ["reproduced here"],
            "affected_stacks": [],
            "affected_models": [],
            "affected_versions_builds": "",
            "known_limitations": "fixture",
            "source_path": "traps/test/91-fixture.md",
            "applicability": {},
        }]}
        result = diagnose(registry, "selected endpoint benchmark mismatch")
        self.assertTrue(result["matches"])
        self.assertEqual("91", result["matches"][0]["trap_id"])
        self.assertIn("possible_unverified_leads", result)
        for lead in result["possible_unverified_leads"]:
            self.assertFalse(lead["canonical"])

    def test_garble_replay_negative_is_retained_without_confirmation(self):
        matches = search_leads("post tool native markup replay")
        l024 = next(item for item in matches if item["lead_id"] == "L024")
        self.assertEqual("REPLAY_DID_NOT_REPRODUCE", l024["evidence_status"])
        self.assertEqual("POSSIBLE_UNVERIFIED_LEAD", l024["lead_match_level"])


if __name__ == "__main__":
    unittest.main()
