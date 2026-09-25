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


class VersionContract(unittest.TestCase):
    def test_runtime_version_matches_package_metadata(self):
        # Plugins pin >=0.2,<0.3; every surface must report the same version.
        import re
        from pathlib import Path

        import minefield

        root = Path(__file__).resolve().parents[1]
        declared = re.search(
            r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(encoding="utf-8"), re.M
        ).group(1)
        self.assertEqual(minefield.__version__, declared)


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


    def test_one_shared_word_is_not_enough_for_canonical_candidate(self):
        # Regression for the pre-0.2 matcher: an ordinary shared word could
        # create a plausible-looking candidate by itself.
        result = api.match_symptom("unrelated")
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["diagnosis_level"], "NOT_DOCUMENTED")

    def test_context_does_not_rescue_one_weak_symptom_word(self):
        result = api.match_symptom("unrelated", stack="vllm")
        self.assertEqual(result["matches"], [])

    def test_common_phrasings_use_synonyms_without_inflating_one_word(self):
        cases = (
            ("empty response at token ceiling", "12"),
            ("garbage output after device map auto", "39"),
            ("thinking leaked into content with thinking false", "126"),
            ("tool choice ignored despite tool call request", "78"),
        )
        for symptom, expected in cases:
            with self.subTest(symptom=symptom):
                result = api.match_symptom(symptom, limit=5)
                ids = {m["trap_ids"][0] for m in result["matches"]}
                self.assertIn(expected, ids)

    def test_log_excerpt_can_supply_additional_matching_evidence(self):
        without_log = api.match_symptom("streamed")
        self.assertEqual(without_log["matches"], [])

        with_log = api.match_symptom(
            "streamed",
            log_excerpt="answer lands in reasoning channel while content stays empty",
            limit=5,
        )
        ids = {m["trap_ids"][0] for m in with_log["matches"]}
        self.assertIn("23", ids)

    def test_miss_is_not_a_safe_verdict(self):
        result = api.match_symptom("zzqxv qqzzw")
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["diagnosis_level"], "NOT_DOCUMENTED")
        self.assertIn("never safe", result["warning"])


if __name__ == "__main__":
    unittest.main()
