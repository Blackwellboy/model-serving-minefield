import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "leads" / "LEADS.json"
ID_RE = re.compile(r"^L\d{3}$")


class LeadCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        cls.leads = cls.payload["leads"]

    def test_catalogue_does_not_change_canonical_count(self):
        self.assertEqual(0, self.payload["canonical_trap_count_impact"])
        self.assertTrue(self.payload["policy"]["lead_match_never_confirms_root_cause"])

    def test_ids_unique_and_stable_shape(self):
        ids = [lead["id"] for lead in self.leads]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(ids)
        for lead_id in ids:
            self.assertRegex(lead_id, ID_RE)

    def test_required_fields_and_statuses(self):
        required = {
            "id", "title", "canonical", "status", "source_class", "scope",
            "symptom", "possible_mechanism", "confirmation_check",
            "refutation_check", "conditional_mitigation", "related_traps",
            "affected_stacks", "source_refs", "confidence", "notes",
        }
        allowed = set(self.payload["allowed_statuses"])
        self.assertTrue(allowed)
        for lead in self.leads:
            self.assertTrue(required <= set(lead), lead["id"])
            self.assertFalse(lead["canonical"], lead["id"])
            self.assertIn(lead["status"], allowed, lead["id"])
            self.assertIn(lead["confidence"], {"low", "medium", "high"}, lead["id"])
            for field in ("title", "symptom", "possible_mechanism",
                          "confirmation_check", "refutation_check"):
                self.assertTrue(str(lead[field]).strip(), f"{lead['id']} {field}")
            self.assertIsInstance(lead["related_traps"], list)
            self.assertIsInstance(lead["source_refs"], list)

    def test_public_catalogue_excludes_private_permission_limited_source_class(self):
        banned = {"private_bilateral_share", "permission_limited_third_party"}
        for lead in self.leads:
            self.assertNotIn(lead["source_class"], banned, lead["id"])


if __name__ == "__main__":
    unittest.main()
