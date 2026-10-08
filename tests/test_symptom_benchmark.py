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

    def test_pasted_lines_floor(self):
        # Log lines copied verbatim from reports. Small n: one case below measured.
        pasted = self.report["pasted_lines"]["all"]
        self.assertGreaterEqual(pasted["top1"], 0.30, pasted)
        self.assertGreaterEqual(pasted["top5"], 0.45, pasted)

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


class DiagnosticFingerprintMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from minefield.registry import load_registry
        cls.registry = load_registry()

    def top(self, query):
        from minefield.matching import search
        results = search(self.registry, query, limit=5)
        self.assertTrue(results, query)
        return results[0]

    def test_memorymax_routes_to_125(self):
        top = self.top("vllm systemd MemoryMax guard never fires")
        self.assertEqual(top["trap_ids"][0], "125")
        self.assertIn("MemoryMax", top["fingerprint_matches"])

    def test_sliding_window_routes_to_143(self):
        top = self.top("Qwen3 sliding_window config but every layer is full attention")
        self.assertEqual(top["trap_ids"][0], "143")
        self.assertIn("sliding_window", top["fingerprint_matches"])

    def test_fuse_gemm_comms_routes_to_117(self):
        top = self.top("vllm startup says fuse_gemm_comms enabled but resolved config says false")
        self.assertEqual(top["trap_ids"][0], "117")
        self.assertIn("fuse_gemm_comms", top["fingerprint_matches"])

    def test_fingerprint_match_is_still_not_confirmed(self):
        top = self.top("vllm systemd MemoryMax")
        self.assertTrue(top["fingerprint_matches"])
        self.assertNotIn("CONFIRMED", top["diagnosis_level"])


class PastedLogLines(unittest.TestCase):
    """A pasted error line goes through the same signatures as a log scan."""

    @classmethod
    def setUpClass(cls):
        import re

        from minefield.log_inspector import RULES
        from minefield.registry import load_registry

        sys.path.insert(0, str(ROOT / "tests"))
        from test_offline_detectors import BAD_LOG, CLEAN_LOG

        cls.registry = load_registry()
        cls.bad = [(line, trap) for line in BAD_LOG.splitlines()
                   for trap, pattern, _ in RULES if re.search(pattern, line, re.I | re.M)]
        cls.clean = CLEAN_LOG.splitlines()

    def search(self, text, **kwargs):
        from minefield.matching import search

        return search(self.registry, text, limit=10, **kwargs)

    def test_each_signature_line_ranks_its_trap_first(self):
        self.assertGreaterEqual(len(self.bad), 10)
        for line, trap in self.bad:
            results = self.search(line)
            self.assertTrue(results, line)
            self.assertEqual(results[0]["trap_ids"][0], trap, line)
            self.assertTrue(results[0]["log_signature"], line)

    def test_harmless_lines_carry_no_signature(self):
        for line in self.clean:
            self.assertFalse([r for r in self.search(line) if r["log_signature"]], line)

    def test_a_wrapped_paste_still_matches(self):
        # Issue #45, as pasted: the terminal wrapped the line mid-sentence.
        wrapped = ("ValueError: Free memory on device cuda:0 (109.53/121.69 GiB) on startup is\n"
                   "less than desired GPU memory utilization (0.91, 110.74 GiB)")
        results = self.search("vllm will not start", log_excerpt=wrapped)
        self.assertEqual(results[0]["trap_ids"][0], "119")
        self.assertTrue(results[0]["log_signature"])

    def test_a_signature_match_stays_a_lead(self):
        line, _ = self.bad[0]
        top = self.search(line)[0]
        self.assertNotIn("CONFIRMED", top["diagnosis_level"])

    def test_cli_labels_it_by_what_matched(self):
        from minefield.render import strength

        line, _ = self.bad[0]
        self.assertEqual(strength(self.search(line)[0]), "log line match")


if __name__ == "__main__":
    unittest.main()
