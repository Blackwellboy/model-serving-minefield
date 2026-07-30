#!/usr/bin/env python3
"""Mutation proof for the contradiction gate.

The gate fires on zero of the 81 entries as they stand, which is the correct
result and also exactly what a broken gate looks like. So every case below
plants a defect and asserts it fires, or plants an honest entry and asserts it
does not.

The honest-entry cases are not padding. An absence-gate over the same corpus
failed 36 of 61 entries, nearly all of them honest, and that is why it was
abandoned; these cases are the regression test for that failure mode.
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INTEGRITY = os.path.dirname(HERE)
REPO = os.path.dirname(INTEGRITY)
sys.path.insert(0, INTEGRITY)
import contradiction_gate as cg  # noqa: E402


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


ENTRY = """# Trap 99: a fixture

**Found by Blackwellboy.**

**Status: {status}** {status_tail}

**Symptom.** Something observable.

**Mechanism.** Something explains it.

**The check.** {check}

**The fix.** Change the thing.

**Found.** 2026-07-28.

**Attribution.** Blackwellboy.{extra}
"""


class ContradictionGate(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "traps", "runtime"))
        os.makedirs(os.path.join(self.root, "mining", "fixture-data"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, body):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        return p

    def entry(self, status="reproduced here.", status_tail="", check="Run it.",
              extra=""):
        return self.write("traps/runtime/99-fixture.md",
                          ENTRY.format(status=status, status_tail=status_tail,
                                       check=check, extra=extra))

    def run_gate(self, p):
        return cg.check(p, self.root, read)

    # --- it must FIRE -----------------------------------------------------

    def test_contradiction_in_the_entry_itself(self):
        p = self.entry(status_tail="The raw is available on request.")
        hits = self.run_gate(p)
        self.assertTrue(hits, "an on-request offer beside reproduced-here passed")
        self.assertIn("on request", hits[0][1])

    def test_contradiction_one_hop_away_which_is_the_trap_33_case(self):
        """The defect that motivated this gate was NOT in the entry. It was in
        the data README the entry links to."""
        self.write("mining/fixture-data/README.md",
                   "# Fixture data\n\nWhat that means for you: you cannot check "
                   "our rows, and you can run the study.\n")
        p = self.entry(check="Everything is in "
                             "[the data](../../mining/fixture-data/README.md).")
        hits = self.run_gate(p)
        self.assertTrue(hits, "the trap-33 shape passed: contradiction one hop away")
        self.assertIn("cannot check our rows", hits[0][1])
        self.assertIn(
            "mining/fixture-data/README.md",
            hits[0][0].replace("\\", "/"),
        )

    def test_entry_reading_only_would_have_missed_it(self):
        """Control for the case above: the entry alone is clean, so a gate that
        did not follow the link would report nothing."""
        self.write("mining/fixture-data/README.md",
                   "# Fixture data\n\nyou cannot check our rows\n")
        p = self.entry(check="See [the data](../../mining/fixture-data/README.md).")
        entry_only = [h for h in self.run_gate(p) if h[0].startswith("traps/")]
        self.assertFalse(entry_only, "fixture drift: the entry itself is dirty")
        self.assertTrue(self.run_gate(p), "the hop is not being followed")

    def test_held_outside_the_tree(self):
        p = self.entry(status_tail="Raw is per-turn JSONL held outside the tree.")
        self.assertTrue(self.run_gate(p))

    # --- it must NOT fire -------------------------------------------------

    def test_honest_prose_procedure_passes(self):
        """The failure mode that killed the absence gate. This entry names no
        URL, no path and no command, and it is fine."""
        p = self.entry(check="Fetch the repository and confirm there is no "
                             "chat_template.jinja, then read the encoder module "
                             "it ships instead.")
        self.assertFalse(self.run_gate(p),
                         "fired on an honest prose procedure, which is the "
                         "regression the absence gate died of")

    def test_compound_status_that_discloses_is_not_a_contradiction(self):
        """Precision must not be punished: an entry that says which half is
        weaker is doing the right thing."""
        p = self.entry(
            status="reproduced here** for the arithmetic and **measured here, "
                   "raw not published",
            status_tail="for the curve. The raw is held outside the tree.")
        self.assertFalse(self.run_gate(p),
                         "fired on a correctly scoped compound status")

    def test_a_labelled_subsection_owns_its_own_admission(self):
        """A folded contributor addendum whose raw is private says so, and is
        labelled contributor-measured. That is the addendum's limit, not the
        host entry's."""
        p = self.entry(extra="\n\n## Added later\n\n**Status: "
                             "contributor-measured, conditions as reported.**\n"
                             "His raw is held outside the tree.\n")
        self.assertFalse(self.run_gate(p),
                         "a labelled sub-section's admission was charged to the "
                         "host entry")

    def test_not_gated_when_the_entry_does_not_claim_reproduced_here(self):
        p = self.entry(status="measured here, raw not published.",
                       status_tail="The raw is available on request.")
        self.assertFalse(self.run_gate(p))

    def test_policy_documents_are_not_followed(self):
        """Every entry links CONTRIBUTING, which discusses non-checkability
        generically. Following it fired on 12 entries when measured."""
        self.write("CONTRIBUTING.md",
                   "# Contributing\n\nThis holds whether your raw is private or "
                   "published at a URL.\n")
        p = self.entry(check="See [CONTRIBUTING](../../CONTRIBUTING.md).")
        self.assertFalse(self.run_gate(p))

    def test_sibling_entries_are_not_followed(self):
        """Another entry's limits are not this entry's contradiction."""
        self.write("traps/runtime/98-other.md",
                   "# Trap 98\n\n**Status: measured here, raw not published.**\n"
                   "The raw is available on request.\n")
        p = self.entry(check="Related: [trap 98](98-other.md).")
        self.assertFalse(self.run_gate(p))

    # --- the whole live tree ---------------------------------------------

    def test_the_real_registry_is_clean(self):
        import glob
        fires = []
        for e in sorted(glob.glob(os.path.join(REPO, "traps", "*", "*.md"))):
            if cg.check(e, REPO, read):
                fires.append(os.path.relpath(e, REPO))
        self.assertFalse(fires, f"contradiction gate fires on live entries: {fires}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
