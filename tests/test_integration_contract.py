"""Contract for downstream integrations (hermes-minefield and friends).

The Hermes plugin read ``load_registry()["traps"]`` while the registry has
always published ``entries``, so its incident matcher returned zero matches on
every call and never said so. These tests pin the surface integrations are
told to use, so a rename here fails loudly in this repo instead of silently in
someone else's.
"""

from __future__ import annotations

import unittest

from minefield import api
from minefield.registry import load_registry


class RegistryShapeContract(unittest.TestCase):
    def test_entries_key_and_fields_integrations_read(self):
        registry = load_registry()
        self.assertIn("entries", registry)
        self.assertNotIn("traps", registry)
        self.assertEqual(len(registry["entries"]), registry["canonical_trap_count"])
        for entry in registry["entries"]:
            for key in ("id", "title", "symptom", "category", "status"):
                self.assertIn(key, entry, entry.get("id"))


class MatchSymptomContract(unittest.TestCase):
    def test_exported(self):
        self.assertIn("match_symptom", api.__all__)

    def test_known_symptom_returns_ranked_candidates_not_confirmations(self):
        result = api.match_symptom(
            "answer lands in the reasoning channel when streaming",
            stack="vllm",
        )
        self.assertTrue(result["matches"])
        ids = {m["trap_ids"][0] for m in result["matches"]}
        self.assertIn("23", ids)
        for match in result["matches"]:
            self.assertNotEqual(match["diagnosis_level"], "CONFIRMED")
        self.assertIn("possible_unverified_leads", result)

    def test_limit_is_respected(self):
        result = api.match_symptom("reasoning template tool parser", limit=2)
        self.assertLessEqual(len(result["matches"]), 2)

    def test_miss_is_not_a_safe_verdict(self):
        result = api.match_symptom("zzqxv qqzzw")
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["diagnosis_level"], "NOT_DOCUMENTED")
        self.assertIn("never safe", result["warning"])


if __name__ == "__main__":
    unittest.main()
