"""Quality floor for the offline symptom matcher.

benchmarks/symptom_queries.json holds two plain-language user phrasings per
trap (tune / holdout), reported cases in reporters' own words from real issues,
and off-domain negatives. These floors sit just under the measured numbers at
the time they were set; a drop below them is a real matcher regression to
investigate, not noise, because the matcher is deterministic. Raise them when
the matcher improves.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from run_symptom_benchmark import DATA, evaluate  # noqa: E402

from minefield.matching import _concepts, _tokens  # noqa: E402


class SymptomBenchmarkFloor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate()
        cls.cases = json.loads(DATA.read_text(encoding="utf-8"))["cases"]

    def test_every_trap_has_a_written_query_in_each_split(self):
        from minefield.registry import load_registry

        ids = {entry["id"] for entry in load_registry()["entries"]}
        for split in ("tune", "holdout"):
            written = [c["trap"] for c in self.cases if c["split"] == split and not c.get("source")]
            self.assertEqual(sorted(written), sorted(ids), split)

    def test_reported_cases_are_sourced_and_balanced(self):
        from minefield.registry import load_registry

        ids = {entry["id"] for entry in load_registry()["entries"]}
        reported = [c for c in self.cases if c.get("source")]
        self.assertTrue(reported)
        for case in reported:
            self.assertRegex(case["source"], r"^issue #\d+$")
            self.assertIn(case["trap"], ids, case)
        self.assertEqual(len({c["source"] for c in reported}), len(reported), "one case per issue")
        tune = sum(c["split"] == "tune" for c in reported)
        self.assertLessEqual(abs(tune - (len(reported) - tune)), 1)

    def test_holdout_quality_floor(self):
        holdout = self.report["splits"]["holdout"]
        self.assertGreaterEqual(holdout["top1"], 0.84, holdout)
        self.assertGreaterEqual(holdout["top5"], 0.88, holdout)

    def test_tune_quality_floor(self):
        tune = self.report["splits"]["tune"]
        self.assertGreaterEqual(tune["top1"], 0.86, tune)
        self.assertGreaterEqual(tune["top5"], 0.94, tune)

    def test_reported_quality_floor(self):
        # Small n: each floor sits one case below the measured count.
        holdout = self.report["reported"]["holdout"]
        self.assertGreaterEqual(holdout["top1"], 0.45, holdout)
        self.assertGreaterEqual(holdout["top5"], 0.55, holdout)
        tune = self.report["reported"]["tune"]
        self.assertGreaterEqual(tune["top1"], 0.45, tune)
        self.assertGreaterEqual(tune["top5"], 0.60, tune)

    def test_off_domain_questions_never_nominate_a_trap(self):
        for name, negatives in self.report["negatives"].items():
            self.assertEqual(negatives["hits"], [], name)


class MatcherTokens(unittest.TestCase):
    def test_sentence_punctuation_does_not_stick_to_a_word(self):
        self.assertEqual(_tokens("Those look like a ranking."), _tokens("Those look like a ranking"))
        self.assertIn("llama.cpp", _tokens("served by llama.cpp."))
        self.assertIn("0.26", _tokens("vLLM 0.26"))

    def test_compound_identifier_meets_its_prose_words(self):
        self.assertLessEqual(_tokens("tool call parser"), _tokens("--tool-call-parser"))
        self.assertLessEqual(_tokens("reasoning tokens"), _tokens("reasoning_tokens"))

    def test_compound_identifier_is_still_one_concept(self):
        concepts = _concepts("--tool-call-parser")
        self.assertEqual(len(concepts), 1, concepts)


if __name__ == "__main__":
    unittest.main()
