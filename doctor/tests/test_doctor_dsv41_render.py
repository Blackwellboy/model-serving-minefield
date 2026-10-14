#!/usr/bin/env python3
"""Doctor verdicts on a DeepSeek-V4.1-shaped lane (mock_dsv41_lane.py).

Found on a live DeepSeek-v4.1-Flash-EXL3 vLLM lane on 2026-10-15, where the
Doctor reported three things the lane's /tokenize render contradicted:

  1. trap 02 PROBLEM "orphaned close tags" for the encoder's own
     `<｜Assistant｜></think>` turn prefix
  2. trap 04 PROBLEM "no preservation path" although every render that defines
     a tool keeps prior reasoning (the agent case)
  3. trap 58 INCONCLUSIVE "no prompt-token change" although the rendered budget
     moved 50 -> 25 -> 100; the named ladder was also shifted from the encoder
     reference, which no check looked at (trap 07)

No real endpoint is contacted.

    python3 -m unittest discover -s doctor/tests -t doctor/tests
"""
import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mock_dsv41_lane import MockLane  # noqa: E402

spec = importlib.util.spec_from_file_location("doc_dsv41", HERE.parent / "minefield_doctor.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(mode):
    with MockLane(mode) as base:
        doc = mod.Doc()
        b = base.rstrip("/")
        root = b[:-3].rstrip("/")
        with redirect_stdout(io.StringIO()):
            assert mod.detect_stack(doc, b, root, None), "mock lane unreachable"
            mod.check_history_assembly(doc, root, None)
            mod.check_reasoning_effort_switch(doc, b, None, root=root)
    return doc


def codes(doc):
    return {f["code"]: f for f in doc.findings}


class TestDeepSeekV41Render(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.served = run("served")
        cls.reference = run("reference")

    def test_encoder_prefix_close_is_not_an_orphan(self):
        self.assertNotIn("ORPHANED_CLOSE_IN_RENDER", codes(self.served))
        bal = self.served.evidence["think_tag_balance"]
        self.assertGreater(bal["encoder_prefix_close"], 0)

    def test_chatml_close_after_assistant_still_counts(self):
        chatml = ("<|im_start|>assistant\n</think>Doing step 1.<|im_end|>\n"
                  "<|im_start|>assistant\n</think>Doing step 2.<|im_end|>\n"
                  "<|im_start|>assistant\n<think>\n")
        excess, counts = mod.orphaned_close_count(chatml)
        self.assertEqual(excess, 1, counts)

    def test_tool_conditional_retention_is_named(self):
        c = codes(self.served)
        self.assertNotIn("HISTORY_STRIPPED_NO_GATE", c)
        f = c.get("HISTORY_STRIPPED_UNLESS_TOOLS")
        self.assertIsNotNone(f, sorted(c))
        self.assertEqual(f["level"], "PROBLEM")
        self.assertIn("04", f["traps"])
        hits = self.served.evidence["write_field_hits_with_tools"]
        self.assertTrue(hits["reasoning_content"] and hits["reasoning"], hits)

    def test_rendered_budget_change_is_seen_despite_flat_token_counts(self):
        c = codes(self.served)
        self.assertNotIn("EFFORT_ACCEPTED_NO_VISIBLE_EFFECT", c)
        f = c.get("EFFORT_CHANGES_PROMPT_OR_REASONING")
        self.assertIsNotNone(f, sorted(c))
        self.assertIn("rendered_prompt", f["title"])

    def test_shifted_ladder_is_reported_with_both_ladders(self):
        f = codes(self.served).get("EFFORT_LADDER_DIVERGES_FROM_REFERENCE")
        self.assertIsNotNone(f)
        self.assertIn("07", f["traps"])
        self.assertEqual(self.served.evidence["reasoning_effort_rendered"]["budgets"],
                         {"default": 50, "low": 25, "high": 50, "max": 100})
        self.assertIn("low -> 25 (reference 50)", f["title"])

    def test_reference_ladder_is_not_flagged(self):
        self.assertNotIn("EFFORT_LADDER_DIVERGES_FROM_REFERENCE", codes(self.reference))

    def test_every_not_clean_verdict_names_a_failed_assertion(self):
        for doc in (self.served, self.reference):
            for f in doc.findings:
                if f["level"] == "OK":
                    self.assertTrue(all(a["result"] == "held" for a in f["assertions"]),
                                    f["code"])
                else:
                    self.assertTrue(any(a["result"] == "failed" for a in f["assertions"]),
                                    f["code"])


if __name__ == "__main__":
    unittest.main()
