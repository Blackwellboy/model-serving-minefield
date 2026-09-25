"""Quality floor for the offline symptom matcher.

benchmarks/symptom_queries.json holds two plain-language user phrasings per
trap (tune / holdout) and off-domain negatives. These floors sit just under
the measured numbers at the time they were set; a drop below them is a real
matcher regression to investigate, not noise, because the matcher is
deterministic. Raise them when the matcher improves.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from run_symptom_benchmark import evaluate  # noqa: E402


class SymptomBenchmarkFloor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate()

    def test_every_trap_has_a_query_in_each_split(self):
        from minefield.registry import load_registry

        ids = {entry["id"] for entry in load_registry()["entries"]}
        for split in ("tune", "holdout"):
            self.assertEqual(self.report["splits"][split]["n"], len(ids), split)

    def test_holdout_quality_floor(self):
        holdout = self.report["splits"]["holdout"]
        self.assertGreaterEqual(holdout["top1"], 0.80, holdout)
        self.assertGreaterEqual(holdout["top5"], 0.90, holdout)

    def test_tune_quality_floor(self):
        tune = self.report["splits"]["tune"]
        self.assertGreaterEqual(tune["top1"], 0.84, tune)
        self.assertGreaterEqual(tune["top5"], 0.95, tune)

    def test_off_domain_questions_never_nominate_a_trap(self):
        for name, negatives in self.report["negatives"].items():
            self.assertEqual(negatives["hits"], [], name)


if __name__ == "__main__":
    unittest.main()
