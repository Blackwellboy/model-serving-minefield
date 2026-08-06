#!/usr/bin/env python3
"""Mutation tests for integrity/reference_integrity.py.

A green run is also what a check that asserts nothing looks like. Each test
below reintroduces a staleness that has actually happened to this repo, or
that a renumber would produce, and asserts the checker FIRES. The clean-tree
test asserts it does not fire otherwise, so the suite fails both ways.

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
CHECKER = os.path.join(INTEGRITY, "reference_integrity.py")


def copy_tree(dst):
    """Copy the parts of the repo the checker reads. Deliberately includes
    .git so tracked_md() takes its normal git path rather than the fallback."""
    # .github is in the list because the PR template restates the status
    # vocabulary, and the restatement is what VOCAB-SLASH and VOCAB-FULL
    # check. Without it those tests would pass against a tree that does not
    # contain the file they exist for.
    # upstream/ is in the list because REF-EXISTS resolves every relative link
    # in every tracked markdown file, and CONTRIBUTING, README, the stack pages
    # and the mining notes all link into it. Omitting it made 48 correct links
    # dangle inside the copy, so five tests failed against a tree that was
    # green. A partial copy is a mutation nobody intended.
    # llms.txt joined the list the day it landed, for the same reason upstream/
    # did: README links to it, REF-EXISTS resolves every relative link in the
    # copy, and a file left out of the copy is a broken link that exists only
    # inside the fixture. Four tests went red against a green tree. The comment
    # above was already describing this exact failure, which is a fair warning
    # that the list is the fragile part: anything the docs link to has to be
    # here, and nothing tells you when that stops being true. The agent product
    # added a root front door, generated dist Markdown, and docs/ links; those
    # are copied for the same reason rather than exempted from link checking.
    for name in ("traps", "playbooks", "stacks", "models", "mining", "upstream",
                 "README.md", "CORE.md", "CHANGELOG.md", "CONTRIBUTING.md",
                 "MAINTAINING.md", "HALL_OF_FAME.md", "SECURITY.md", "llms.txt",
                 "AGENT_START_HERE.md", "dist", "docs", "doctor", "checks",
                 "community", "integrity", ".github", "LICENSE"):
        src = os.path.join(ROOT, name)
        if not os.path.exists(src):
            continue
        d = os.path.join(dst, name)
        if os.path.isdir(src):
            shutil.copytree(src, d, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, d)
    subprocess.run(["git", "init", "-q", dst], check=True)
    subprocess.run(["git", "-C", dst, "add", "-A"], check=True,
                   capture_output=True)
    return dst


def run_checker(root):
    p = subprocess.run([sys.executable, CHECKER, "--root", root],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def find_entry(root, tid):
    traps = os.path.join(root, "traps")
    for d in sorted(os.listdir(traps)):
        full = os.path.join(traps, d)
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if f.startswith(tid + "-") and f.endswith(".md"):
                return os.path.join(full, f)
    raise AssertionError("no entry %s" % tid)


class ReferenceMutations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="refint-")
        self.repo = copy_tree(os.path.join(self.tmp, "repo"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_00_clean_tree_passes(self):
        """The control. If this fails, every mutation below proves nothing."""
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 0, "clean tree should pass:\n" + out)
        self.assertIn("CLEAN", out)

    def test_01_playbook_citing_a_number_that_moved(self):
        """The renumber case. A playbook cites trap 91; the entry is gone."""
        os.remove(find_entry(self.repo, "91"))
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("ROUTING-ID", out)

    def test_02_model_index_missing_an_entry_is_NOT_this_checker(self):
        """Honesty test. entry -> index is registry_integrity's INDEX check,
        not this one. This checker owns the reverse direction. If someone
        later makes this fire here, the residual list is wrong."""
        p = os.path.join(self.repo, "models", "README.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace(
            "[93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md)",
            "")
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 0, "reverse-direction checker must stay quiet "
                                "on a missing index row:\n" + out)

    def test_03_dangling_link_on_a_stack_page(self):
        """stacks/ is outside registry_integrity's nine-file link list."""
        p = os.path.join(self.repo, "stacks", "llama-cpp.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("../traps/runtime/91-", "../traps/runtime/9001-", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("REF-EXISTS", out)

    def test_04_dangling_link_in_a_playbook(self):
        p = os.path.join(self.repo, "playbooks", "before-you-publish-an-ab.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("../traps/evaluation/35-", "../traps/evaluation/350-", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("REF-EXISTS", out)

    def test_05_dangling_link_in_CORE(self):
        p = os.path.join(self.repo, "CORE.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("traps/template/04-", "traps/template/404-", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("REF-EXISTS", out)

    def test_06_label_and_href_disagree_after_a_renumber(self):
        """The text says [42], the href goes to 43. Both resolve, so a link
        checker alone never sees it."""
        p = os.path.join(self.repo, "CORE.md")
        t = open(p, encoding="utf-8").read()
        t += ("\n- [42](traps/evaluation/"
              "31-leftover-oracle-reranker.md) renumber artifact\n")
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("REF-NUMBER", out)

    def test_07_status_drifts_on_the_README_row(self):
        """The exact drift found on the live tip: a surface row dropping the
        entry's leading label, which erases a contributor's credit."""
        p = os.path.join(self.repo, "README.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace(
            "[01](traps/reasoning/01-reasoning-field-two-names.md) | reproduced here |",
            "[01](traps/reasoning/01-reasoning-field-two-names.md) | reported by others |",
            1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("STATUS-LEAD", out)

    def test_08_status_drifts_on_CORE(self):
        p = os.path.join(self.repo, "CORE.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace(
            "traps/template/04-history-reasoning-stripping.md) | reproduced here |",
            "traps/template/04-history-reasoning-stripping.md) | under test |",
            1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("STATUS-LEAD", out)

    def test_09_qualifier_prose_does_not_fire(self):
        """The false-positive guard. Round 2 of building this fired on 26
        entries because it matched negated mentions inside status prose. A
        qualifier after the leading stem must stay silent."""
        p = os.path.join(self.repo, "README.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace(
            "[01](traps/reasoning/01-reasoning-field-two-names.md) | reproduced here |",
            "[01](traps/reasoning/01-reasoning-field-two-names.md) | "
            "reproduced here on three stacks, and explicitly not "
            "contributor-measured |", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 0, "a trailing qualifier must not fire:\n" + out)

    # --- the status vocabulary, defined once and restated in four places ----
    #
    # These exist because the PR template shipped for weeks teaching three of
    # the five labels, missing exactly the two an external contribution needs,
    # and that omission is what made the registry's first external
    # contribution arrive mislabelled. CONTRIBUTING was corrected. Nothing
    # asserted the template agreed with it, so the template kept teaching the
    # wrong set. Each test below reintroduces one shape of that drift.

    def test_11_pr_template_teaching_a_partial_slash_list(self):
        """The exact historical defect: a slash-joined subset."""
        p = os.path.join(self.repo, ".github", "PULL_REQUEST_TEMPLATE.md")
        open(p, "w", encoding="utf-8").write(
            "# Adding a trap entry\n\n"
            "- [ ] Status line up top: reproduced here / reported by others / "
            "under test\n")
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("VOCAB-SLASH", out)
        self.assertIn("contributor-measured", out)

    def test_12_slash_list_is_clean_when_it_is_the_whole_set(self):
        """A surface may enumerate with slashes; it may not enumerate a
        SUBSET. Without this the check would just ban a punctuation mark."""
        p = os.path.join(self.repo, ".github", "PULL_REQUEST_TEMPLATE.md")
        t = open(p, encoding="utf-8").read()
        t += ("\n\nStatus: reproduced here / contributor-measured, conditions "
              "as reported / reported by others / measured here, raw not "
              "published / under test\n")
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 0, "a complete slash list must not fire:\n" + out)

    def test_13_marked_surface_dropping_a_label(self):
        p = os.path.join(self.repo, "MAINTAINING.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("**measured here, raw not published**,", "", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("VOCAB-FULL", out)
        self.assertIn("measured here, raw not published", out)

    def test_14_wrapped_label_on_a_marked_surface_is_clean(self):
        """Regression. MAINTAINING wraps 'contributor-measured, conditions as
        reported' across a newline. The first version of this check did a flat
        substring test and reported that present, correct label as missing.
        A guard that fires on an honest surface gets waved through."""
        p = os.path.join(self.repo, "README.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("**contributor-measured,\nconditions as reported**",
                      "**contributor-measured,\n   conditions   as\nreported**", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 0, "wrapped labels must not fire:\n" + out)

    def test_15_gate_labels_diverging_from_the_published_table(self):
        """contradiction_gate enforces the set at runtime. If its list and
        CONTRIBUTING's table disagree, one of them is lying to a
        contributor."""
        p = os.path.join(self.repo, "integrity", "contradiction_gate.py")
        t = open(p, encoding="utf-8").read()
        t = t.replace('    "under test",\n', "", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("VOCAB-GATE", out)

    def test_16_gate_carrying_a_label_nobody_published(self):
        p = os.path.join(self.repo, "integrity", "contradiction_gate.py")
        t = open(p, encoding="utf-8").read()
        t = t.replace('    "under test",\n',
                      '    "under test",\n    "measured on our fleet",\n', 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("VOCAB-GATE", out)
        self.assertIn("measured on our fleet", out)

    def test_17_a_sixth_label_added_to_the_canonical_table(self):
        """Adding a label to CONTRIBUTING must break every stale restatement
        rather than diverge from them silently. This is the direction the
        original defect ran in."""
        p = os.path.join(self.repo, "CONTRIBUTING.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace(
            "| **under test** |",
            "| **vendor-confirmed** | the vendor acknowledged it | a vendor |\n"
            "| **under test** |", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("VOCAB", out)

    def test_18_canonical_table_going_missing(self):
        """No parsable table is reported, not treated as nothing to check."""
        p = os.path.join(self.repo, "CONTRIBUTING.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("## Status vocabulary", "## Statuses", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("VOCAB-DEFN", out)

    def test_19_mining_note_citing_a_dead_id(self):
        p = os.path.join(self.repo, "mining", "OPEN_QUESTIONS.md")
        t = open(p, encoding="utf-8").read()
        t = t.replace("../traps/runtime/97-", "../traps/runtime/970-", 1)
        open(p, "w", encoding="utf-8").write(t)
        rc, out = run_checker(self.repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("REF-EXISTS", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
