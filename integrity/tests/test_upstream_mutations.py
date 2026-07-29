#!/usr/bin/env python3
"""Mutation tests for integrity/upstream_integrity.py.

The upstream tier's whole safety story is that its requirements are enforced
rather than observed. A checker that prints CLEAN and has never been shown to
fire is indistinguishable from a checker that asserts nothing, which is the
defect class this repo has already found in its own tooling three times.

So every assertion the checker makes gets a mutation here that removes or
corrupts exactly the thing it guards, and the test asserts the checker FIRES
with the right check id. `test_clean_tree_passes` asserts it does not fire
otherwise, so the suite fails in both directions.

Every mutation is applied to a COPY of the tree in a temp dir. Nothing here
touches the working tree.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INTEGRITY = os.path.dirname(HERE)
ROOT = os.path.dirname(INTEGRITY)
CHECKER = os.path.join(INTEGRITY, "upstream_integrity.py")


def copy_tree(dst):
    for name in ("upstream", "traps", "README.md", "CORE.md", "CONTRIBUTING.md",
                 "doctor", "integrity"):
        src = os.path.join(ROOT, name)
        if not os.path.exists(src):
            continue
        d = os.path.join(dst, name)
        if os.path.isdir(src):
            shutil.copytree(src, d, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, d)
    return dst


def run_checker(root):
    p = subprocess.run([sys.executable, CHECKER, "--root", root],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def an_entry(root):
    """Path to one upstream entry. Chosen by sort order rather than by name so
    this does not need editing when entries are added or renamed."""
    d = os.path.join(root, "upstream")
    for fn in sorted(os.listdir(d)):
        if re.match(r"^U\d{2,}-.+\.md$", fn):
            return os.path.join(d, fn)
    raise AssertionError("no upstream entry found in the copied tree")


def edit(path, old, new, count=1):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    assert old in text, "mutation target not found: %r" % old[:60]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new, count))


def sub(path, pattern, repl, flags=re.M):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    assert n == 1, "mutation pattern did not match: %r" % pattern
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out)


class UpstreamMutations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mf-upstream-")
        self.root = copy_tree(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- the control -----------------------------------------------------

    def test_clean_tree_passes(self):
        """Without this the suite proves only that the checker can say no."""
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("CLEAN", out)

    # --- US-PRIMARY: the whole reason the tier is publishable -------------

    def test_missing_primary_source_section_fires(self):
        sub(an_entry(self.root), r"^\*\*Primary source", "**Sources")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-PRIMARY", out)

    def test_primary_source_without_a_link_fires(self):
        """A named issue is not a source a reader can open."""
        p = an_entry(self.root)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        text = re.sub(r"https?://[^\s)>\]]+", "an upstream tracker", text)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-PRIMARY", out)

    def test_undated_primary_source_fires(self):
        """An undated link does not record that anybody opened it, which is
        the requirement. This is the mining-list-as-source failure."""
        sub(an_entry(self.root), r"[Rr]ead on\s+\d{4}-\d{2}-\d{2}", "Read")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-PRIMARY", out)

    def test_hard_wrapped_read_on_date_still_passes(self):
        """The regression that this checker shipped with. 'read on' and its
        date land on separate lines in entries that are hard-wrapped, and a
        single-space pattern failed 4 of the first 11 entries, every one of
        them correctly dated. A checker that fires on correct entries gets
        waved through, which is worse than no checker."""
        p = an_entry(self.root)
        sub(p, r"[Rr]ead on\s+(\d{4}-\d{2}-\d{2})", r"Read on\n\1")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 0, out)

    # --- US-REPORTER, US-ENGAGE, US-STATE --------------------------------

    def test_missing_reporter_fires(self):
        sub(an_entry(self.root), r"^\*\*Reported by\b", "**Found by")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-REPORTER", out)

    def test_missing_engagement_fires(self):
        sub(an_entry(self.root), r"^\*\*Maintainer engagement:.*$", "")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-ENGAGE", out)

    def test_engagement_outside_the_vocabulary_fires(self):
        """Free prose here would let 'a maintainer looked at it' and 'a
        maintainer reproduced it' read alike."""
        sub(an_entry(self.root), r"^\*\*Maintainer engagement:.*$",
            "**Maintainer engagement: the team seemed interested.**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-ENGAGE", out)

    def test_missing_issue_state_fires(self):
        sub(an_entry(self.root), r"^\*\*Issue state:.*$", "")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-STATE", out)

    def test_issue_state_outside_the_vocabulary_fires(self):
        sub(an_entry(self.root), r"^\*\*Issue state:.*$",
            "**Issue state: probably still a problem.**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-STATE", out)

    def test_closed_stale_may_not_be_written_as_closed_fixed(self):
        """The specific conflation the state vocabulary exists to prevent.
        'closed, not fixed' is a value; 'closed (stale)' is not, so an author
        reaching for a casual phrasing is stopped rather than silently
        upgrading a stale close into a fix."""
        sub(an_entry(self.root), r"^\*\*Issue state:.*$",
            "**Issue state: closed (stale bot).**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-STATE", out)

    def test_qualified_state_still_passes(self):
        """'closed, fixed in v0.20.7-rc1' must pass: the vocabulary fixes the
        opening, and the qualifier after it is where the useful part is."""
        sub(an_entry(self.root), r"^\*\*Issue state:.*$",
            "**Issue state: closed, fixed in v9.9.9 by PR #1234.**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 0, out)

    # --- US-STATUS: no measurement claims from inside this tier -----------

    def test_missing_label_fires(self):
        sub(an_entry(self.root), r"^\*\*Status:.*$", "**Status: reported.**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-STATUS", out)

    def test_compound_status_claiming_measurement_fires(self):
        """The failure that would make the tier dangerous: an entry in the
        unmeasured directory claiming it was measured."""
        sub(an_entry(self.root), r"^\*\*Status:.*$",
            "**Status: upstream-reported + reproduced here.**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-STATUS", out)

    def test_compound_with_contributor_measured_fires(self):
        sub(an_entry(self.root), r"^\*\*Status:.*$",
            "**Status: upstream-reported, contributor-measured.**")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-STATUS", out)

    # --- US-NOTREPRO and US-INVITE ---------------------------------------

    def test_missing_not_reproduced_sentence_fires(self):
        p = an_entry(self.root)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        text = re.sub(
            r"(?i)(nobody here has reproduced|we have not reproduced|"
            r"not reproduced here|no one here has reproduced|"
            r"has not been reproduced here)", "we looked at", text)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-NOTREPRO", out)

    def test_missing_invitation_fires(self):
        sub(an_entry(self.root), r"^## If you have this stack.*$",
            "## Notes")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-INVITE", out)

    def test_invitation_without_confirm_fires(self):
        p = an_entry(self.root)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        head, sep, tail = text.partition("## If you have this stack")
        self.assertTrue(sep)
        tail = tail.replace("**CONFIRM", "**Expected")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(head + sep + tail)
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-INVITE", out)

    def test_invitation_without_refute_fires(self):
        p = an_entry(self.root)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        head, sep, tail = text.partition("## If you have this stack")
        self.assertTrue(sep)
        tail = tail.replace("**REFUTE", "**Otherwise")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(head + sep + tail)
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-INVITE", out)

    # --- the three separations -------------------------------------------

    def test_core_citing_an_upstream_entry_fires(self):
        core = os.path.join(self.root, "CORE.md")
        with open(core, "a", encoding="utf-8") as fh:
            fh.write("\n| U01, an upstream report | upstream-reported | no |\n")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-NOT-CORE", out)

    def test_upstream_id_in_doctor_trap_paths_fires(self):
        doc = os.path.join(self.root, "doctor", "minefield_doctor.py")
        with open(doc, encoding="utf-8") as fh:
            text = fh.read()
        out_text, n = re.subn(r"(TRAP_PATHS\s*=\s*\{)",
                              r'\1\n    "U01": "upstream/U01.md",', text,
                              count=1)
        self.assertEqual(n, 1)
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write(out_text)
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-NOT-DOCTOR", out)

    def test_upstream_entry_filed_under_traps_fires(self):
        """The count-inflation route. Registry totals are derived from
        traps/<category>/NN-*.md, so this asserts the construction rather
        than trusting it."""
        src = an_entry(self.root)
        shutil.copy2(src, os.path.join(self.root, "traps", "tools",
                                       "U01-smuggled-in.md"))
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-NOT-COUNTED", out)

    # --- US-GRANDFATHER: the boundary that stops the tier being decorative

    def test_new_reported_by_others_entry_in_traps_fires(self):
        """Without this the easy path for the next upstream-sourced report is
        traps/ with the old label, and the directory separation the tier is
        built on never gets used."""
        target = os.path.join(self.root, "traps", "tools",
                              "99-a-new-upstream-report.md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("# Trap 99: something somebody said\n\n"
                     "**Found by @nobody.**\n\n"
                     "**Status: reported by others** (an upstream issue).\n")
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("US-GRANDFATHER", out)

    def test_grandfathered_entries_do_not_fire(self):
        """The 23 that predate the tier are not a backlog of failures. If this
        ever fires, the snapshot in registry_config.json has gone stale and
        the fix is the config, not the entries."""
        rc, out = run_checker(self.root)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("US-GRANDFATHER", out)


if __name__ == "__main__":
    unittest.main()
