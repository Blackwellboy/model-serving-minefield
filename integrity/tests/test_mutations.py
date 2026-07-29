#!/usr/bin/env python3
"""test_mutations.py - prove the checks have teeth.

A green run proves nothing. Two of this session's predecessors found dead
tests exactly this way, so every check here is exercised by reintroducing the
historical failure it exists to catch, on a throwaway copy of the real tree,
and asserting that the check fails AND that the message names the file and the
missing thing.

Each mutation also carries its negative control: the same assertion on the
unmutated tree, so a check that fails for an unrelated reason cannot be
mistaken for a check that works.

    python3 -m unittest discover -s integrity/tests -t .

The peer repo (laguna-s21-lab) is found next to this one, or via
MINEFIELD_PEER_REPO. Tests that need it skip loudly when it is absent rather
than passing without it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

NL = chr(10)
BT = chr(96)

HERE = os.path.dirname(os.path.abspath(__file__))
INTEGRITY = os.path.dirname(HERE)
REPO = os.path.dirname(INTEGRITY)
PY = sys.executable or "python3"


def peer_repo():
    env = os.environ.get("MINEFIELD_PEER_REPO")
    if env and os.path.isdir(env):
        return env
    guess = os.path.join(os.path.dirname(REPO), "laguna-s21-lab")
    return guess if os.path.isdir(guess) else None


def copy_tree(dest):
    shutil.copytree(REPO, dest,
                    ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dest


def entry_numbers(root):
    """The numbered entries in a tree, derived rather than declared.

    Counts only files under a category directory, so the seven flat redirect
    stubs at traps/*.md are excluded, which is the same rule the checker
    applies. Three tests here used to hard-code 42 and 41 and had to be edited
    by hand every time an entry landed; a count that has to be maintained by
    hand is exactly the drift these tests exist to catch.
    """
    nums = set()
    traps = os.path.join(root, "traps")
    for cat in sorted(os.listdir(traps)):
        d = os.path.join(traps, cat)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            m = re.match(r"^(\d+)-.+\.md$", name)
            if m:
                nums.add(int(m.group(1)))
    return nums


def entry_count(root):
    return len(entry_numbers(root))


def next_free(root):
    return max(entry_numbers(root)) + 1


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(s)


def run_registry(root):
    r = subprocess.run([PY, os.path.join(root, "integrity",
                                         "registry_integrity.py"),
                        "--root", root, "--json"],
                       capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def run_claims(ledger, repos, extra_root=None):
    cmd = [PY, os.path.join(INTEGRITY, "claim_propagation.py"),
           "--ledger", ledger, "--json"]
    for k, v in repos.items():
        cmd += ["--repo", "%s=%s" % (k, v)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"stdout": r.stdout}


def findings_of(payload, check):
    return [f for f in payload["findings"] if f["check"] == check]


class RegistryMutations(unittest.TestCase):
    """Every historical registry failure, reintroduced."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="minefield-mut-")
        self.root = copy_tree(os.path.join(self.tmp, "repo"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_00_clean_tree_is_clean_except_known(self):
        """Negative control for everything below: the unmutated tree produces
        no finding of any of the classes the mutations produce."""
        rc, out = run_registry(self.root)
        for check in ("README-ROW", "COUNT", "CHANGELOG", "LINKS", "STUBS",
                      "FILE-STATUS", "README-STATUS", "FOUND-BY"):
            self.assertEqual(findings_of(out, check), [],
                             "unmutated tree already fails %s; the mutation "
                             "tests below cannot distinguish signal from that"
                             % check)

    def test_01_trap_missing_its_readme_row(self):
        """The launch-document failure: an entry exists, the symptom table
        does not know about it."""
        p = os.path.join(self.root, "README.md")
        text = read(p)
        target = "traps/routing/33-moe-inference-topk-expansion-tax.md"
        lines = [l for l in text.splitlines()
                 if not (l.startswith("| You gave a MoE") and target in l)]
        self.assertEqual(len(lines), len(text.splitlines()) - 1,
                         "fixture drift: the trap 33 README row moved")
        write(p, "\n".join(lines) + "\n")

        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        rows = findings_of(out, "README-ROW")
        self.assertEqual(len(rows), 1)
        self.assertIn("33-moe-inference-topk-expansion-tax.md", rows[0]["where"])
        self.assertIn("symptom table", rows[0]["message"])

    def test_02_stale_count_in_the_doctor_constant(self):
        """The stale-count failure, constant side."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "doctor", "minefield_doctor.py")
        before = read(p)
        after = before.replace("REGISTRY_TRAP_COUNT = %d" % n,
                               "REGISTRY_TRAP_COUNT = %d" % (n - 1))
        self.assertNotEqual(before, after,
                            "fixture drift: the doctor constant does not read "
                            "REGISTRY_TRAP_COUNT = %d for a tree of %d entries"
                            % (n, n))
        write(p, after)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        counts = findings_of(out, "COUNT")
        self.assertTrue(any("minefield_doctor.py" in f["where"] for f in counts))
        self.assertTrue(any("declares registry total %d" % (n - 1) in f["message"]
                            and "tree has %d" % n in f["message"] for f in counts),
                        counts)

    def test_03_stale_count_in_a_launch_document(self):
        """The stale-count failure, prose side: a new entry lands and the
        README coverage sentence keeps the old total."""
        n = entry_count(self.root)
        free = next_free(self.root)
        write(os.path.join(self.root, "traps", "routing",
                           "%d-a-new-entry-for-the-mutation-test.md" % free),
              "# Trap %d: fixture\n\n**Found by Blackwellboy.**\n\n"
              "**Status: reproduced here** (fixture).\n" % free)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        counts = findings_of(out, "COUNT")
        wheres = " ".join(f["where"] for f in counts)
        self.assertIn("README.md", wheres)
        self.assertIn("doctor/README.md", wheres)
        self.assertIn("doctor/minefield_doctor.py", wheres)
        self.assertTrue(any("tree has %d entries" % (n + 1) in f["message"]
                            for f in counts), counts)

    def test_04_redirect_stubs_are_counted_as_entries(self):
        """The counting rule itself. If the seven flat stubs were ever counted
        as entries the total would read seven too high and every count check
        would invert. This asserts the tool's own arithmetic, which is the
        thing all the other count assertions rest on.

        Both sides are derived from the tree: the expected entry count from the
        category directories, and the stub count from the flat files. A
        hard-coded number here would make this test agree with the checker by
        being edited alongside it, which is not agreement."""
        stubs = len([n for n in os.listdir(os.path.join(self.root, "traps"))
                     if re.match(r"^\d+-.+\.md$", n)])
        rc, out = run_registry(self.root)
        self.assertEqual(out["entries"], entry_count(self.root))
        self.assertEqual(out["stubs"], stubs)
        self.assertGreater(out["entries"], out["stubs"],
                           "stubs are being counted as entries")

    def test_05_entry_not_announced_in_the_changelog(self):
        p = os.path.join(self.root, "CHANGELOG.md")
        text = read(p)
        write(p, text.replace(
            "traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md",
            "traps/evaluation/00-removed-by-mutation.md"))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        cl = findings_of(out, "CHANGELOG")
        self.assertEqual(len(cl), 1)
        self.assertIn("42-single-turn", cl[0]["where"])

    def test_06_broken_internal_link(self):
        p = os.path.join(self.root, "traps", "reasoning",
                         "01-reasoning-field-two-names.md")
        write(p, read(p) + "\n\nSee [the fix](../template/99-does-not-exist.md).\n")
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        links = findings_of(out, "LINKS")
        self.assertTrue(any("99-does-not-exist.md" in f["message"] for f in links),
                        links)

    def test_07_redirect_stub_points_nowhere(self):
        p = os.path.join(self.root, "traps", "01-reasoning-field-two-names.md")
        write(p, read(p).replace("reasoning/01-reasoning-field-two-names.md",
                                 "reasoning/01-moved-again.md"))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        stubs = findings_of(out, "STUBS")
        self.assertTrue(any("01-moved-again.md" in f["message"] for f in stubs),
                        stubs)

    def test_08_third_party_finder_loses_their_credit(self):
        """The failure this suite found for real on the live tree."""
        p = os.path.join(self.root, "HALL_OF_FAME.md")
        write(p, read(p).replace("@Hikari_07_jp", "@someone-else"))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        credit = findings_of(out, "CREDIT")
        self.assertTrue(any("@Hikari_07_jp" in f["message"] for f in credit),
                        credit)

    def test_09_status_word_outside_the_vocabulary(self):
        """The status-word failure: a status that means something different
        from every other entry's status."""
        p = os.path.join(self.root, "traps", "routing",
                         "33-moe-inference-topk-expansion-tax.md")
        write(p, read(p).replace("**Status: reported by others",
                                 "**Status: pretty much confirmed"))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        st = findings_of(out, "FILE-STATUS")
        self.assertTrue(any("33-moe" in f["where"] for f in st), st)

    def test_10_readme_status_cell_outside_the_vocabulary(self):
        p = os.path.join(self.root, "README.md")
        write(p, read(p).replace(
            "| [41](traps/runtime/41-static-batching-buys-power-not-throughput.md) | reported by others |",
            "| [41](traps/runtime/41-static-batching-buys-power-not-throughput.md) | mostly true |"))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        st = findings_of(out, "README-STATUS")
        self.assertTrue(any("mostly true" in f["message"] for f in st), st)

    def test_11_entry_loses_its_found_by_line(self):
        p = os.path.join(self.root, "traps", "routing",
                         "33-moe-inference-topk-expansion-tax.md")
        text = read(p)
        write(p, re.sub(r"\*\*Found by[^\n]*\n(\([^\n]*\n)?", "", text, count=1))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        fb = findings_of(out, "FOUND-BY")
        self.assertTrue(any("33-moe" in f["where"] for f in fb), fb)


    # --- captured-output exemption under mining/ ---------------------------
    #
    # A mining note records a run. When it pastes the coverage line a tool
    # printed, that number must keep saying what it printed. The exemption is
    # narrow on purpose and these four fixtures pin it: the capture passes,
    # and prose in the same file, a README count and a code span outside
    # mining/ all still fail.

    def test_46_captured_output_in_a_mining_note_is_exempt(self):
        """POSITIVE: a stale count inside a code span under mining/ passes,
        because it is a capture of what a tool printed on a date."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-captured-run.md")
        body = NL.join([
            "# A dated run", "",
            "The doctor printed:", "",
            "| Arm | Coverage line |", "|---|---|",
            "| one | `implemented 19/%d | not implemented 84` |" % (n - 4),
        ]) + NL
        write(p, body)
        rc, out = run_registry(self.root)
        counts = [f for f in findings_of(out, "COUNT")
                  if "2026-01-01-captured-run.md" in f["where"]]
        self.assertEqual(counts, [], "a captured coverage line under mining/ "
                                     "must not be read as a live claim: %s" % counts)

    def test_47_prose_in_a_mining_note_is_NOT_exempt(self):
        """NEGATIVE: the same stale number as ordinary prose in the same
        directory is a current assertion and must still fail."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-prose-claim.md")
        body = NL.join(["# A summary", "",
                        "The doctor covers 19 of these %d entries." % (n - 4)]) + NL
        write(p, body)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        counts = [f for f in findings_of(out, "COUNT")
                  if "2026-01-01-prose-claim.md" in f["where"]]
        self.assertTrue(counts, "prose in a mining note is a live claim and "
                               "must still be enforced")

    def test_48_readme_count_is_never_exempt(self):
        """NEGATIVE: the exemption is scoped to mining/ and must not leak."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "README.md")
        text = read(p)
        after = text.replace("All %d entries" % n, "All %d entries" % (n - 4), 1)
        self.assertNotEqual(text, after, "fixture drift: README All N entries")
        write(p, after)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        self.assertTrue(any("README.md" in f["where"]
                            for f in findings_of(out, "COUNT")))

    def test_49_code_span_outside_mining_is_never_exempt(self):
        """NEGATIVE: backticks are not on their own a licence. The same
        capture-shaped line outside mining/ is still enforced."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "doctor", "SCRATCH_NOTE.md")
        body = NL.join(["# scratch", "", "`implemented 19/%d`" % (n - 4)]) + NL
        write(p, body)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        self.assertTrue(any("SCRATCH_NOTE.md" in f["where"]
                            for f in findings_of(out, "COUNT")))



    # Three Markdown-parsing edge cases Codex found on the first version of
    # this rule. Two of them widened the exemption, which is the dangerous
    # direction: an over-strict rule annoys, an over-loose one lets a stale
    # live claim through.

    def test_50_indented_backticks_are_not_a_fence(self):
        """Four or more leading spaces is an indented code block, not a fence.
        Treating it as one would flip fence state and exempt every live count
        claim after it."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-indented.md")
        body = NL.join(["# note", "",
                        "    " + BT * 3,
                        "", "The doctor covers 19 of these %d entries." % (n - 4)]) + NL
        write(p, body)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        self.assertTrue(any("2026-01-01-indented.md" in f["where"]
                            for f in findings_of(out, "COUNT")),
                        "an indented backtick line must not open a fence")

    def test_51_tilde_fenced_capture_is_exempt(self):
        """Tilde fences are valid Markdown and carry captured output too."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-tilde.md")
        body = NL.join(["# note", "", "~~~",
                        "implemented 19/%d" % (n - 4),
                        "~~~"]) + NL
        write(p, body)
        rc, out = run_registry(self.root)
        counts = [f for f in findings_of(out, "COUNT")
                  if "2026-01-01-tilde.md" in f["where"]]
        self.assertEqual(counts, [], "a tilde-fenced capture must be exempt")

    def test_52_escaped_backticks_do_not_make_a_code_span(self):
        """Escaped backticks render literally. Counting them would let prose
        masquerade as captured output."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-escaped.md")
        esc = chr(92) + BT
        body = NL.join(["# note", "",
                        "Prose with " + esc + "implemented 19/%d" % (n - 4) + esc + " inline."]) + NL
        write(p, body)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        self.assertTrue(any("2026-01-01-escaped.md" in f["where"]
                            for f in findings_of(out, "COUNT")),
                        "escaped backticks must not open a code span")


    def test_53_multi_backtick_code_span_is_exempt(self):
        """A code span is delimited by EQUAL-LENGTH backtick runs. Captured
        output often needs the double form because it contains a backtick."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-multitick.md")
        inner = BT + "field" + BT
        line = BT*2 + "implemented 19/%d with %s " % (n - 4, inner) + BT*2
        write(p, NL.join(["# note", "", line]) + NL)
        rc, out = run_registry(self.root)
        counts = [f for f in findings_of(out, "COUNT")
                  if "2026-01-01-multitick.md" in f["where"]]
        self.assertEqual(counts, [], "a multi-backtick capture must be exempt")

    def test_54_longer_fence_is_not_closed_by_a_shorter_inner_one(self):
        """A closing fence must be at least as long as the opener, so a three
        backtick line inside a four backtick block is content, not a close."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-nested.md")
        write(p, NL.join(["# note", "",
                          BT*4,
                          BT*3 + "text",
                          "implemented 19/%d" % (n - 4),
                          BT*3,
                          BT*4]) + NL)
        rc, out = run_registry(self.root)
        counts = [f for f in findings_of(out, "COUNT")
                  if "2026-01-01-nested.md" in f["where"]]
        self.assertEqual(counts, [], "an inner shorter fence must not close "
                                     "the outer block: %s" % counts)


    def test_55_invalid_backtick_info_string_does_not_open_a_fence(self):
        """A backtick fence info string may not contain a backtick. Opening on
        one would exempt every live claim after it, which is a leak."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-infostring.md")
        write(p, NL.join(["# note", "",
                          BT*3 + "python" + BT + "example",
                          "", "The doctor covers 19 of these %d entries." % (n - 4)]) + NL)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        self.assertTrue(any("2026-01-01-infostring.md" in f["where"]
                            for f in findings_of(out, "COUNT")),
                        "an invalid backtick info string must not open a fence")

    def test_56_closing_fence_must_be_bare(self):
        """Non-whitespace after the delimiter means content, not a close."""
        n = entry_count(self.root)
        p = os.path.join(self.root, "mining", "2026-01-01-bareclose.md")
        write(p, NL.join(["# note", "", "~~~",
                          "~~~ still running",
                          "implemented 19/%d" % (n - 4),
                          "~~~"]) + NL)
        rc, out = run_registry(self.root)
        counts = [f for f in findings_of(out, "COUNT")
                  if "2026-01-01-bareclose.md" in f["where"]]
        self.assertEqual(counts, [], "a non-bare delimiter line is content: %s" % counts)


    # --- doctor-coverage prose in mining/OPEN_QUESTIONS.md ---------------
    #
    # This sentence drifted to "19 of 97 / 78 uncovered" while the tree grew
    # to 107, because its bold spans BOTH numbers and no pattern required
    # that shape, and because "uncovered" states the DIFFERENCE rather than a
    # total. Two patterns now cover it. These fixtures pin both, and pin that
    # each fails for its own assertion rather than for the other one.

    def _oq(self):
        return os.path.join(self.root, "mining", "OPEN_QUESTIONS.md")

    def test_57_correct_coverage_prose_passes(self):
        """POSITIVE: the corrected sentence produces no COUNT finding."""
        rc, out = run_registry(self.root)
        counts = [f for f in findings_of(out, "COUNT")
                  if "OPEN_QUESTIONS.md" in f["where"]]
        self.assertEqual(counts, [], "clean tree must not flag the prose: %s" % counts)

    def test_58_stale_registry_total_fails(self):
        """NEGATIVE: 107 -> 97 fails, and names the TOTAL assertion."""
        n = entry_count(self.root)
        t = read(self._oq())
        after = t.replace("**19 of %d** entries" % n, "**19 of %d** entries" % (n - 10), 1)
        self.assertNotEqual(t, after, "fixture drift: coverage sentence")
        write(self._oq(), after)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        hits = [f for f in findings_of(out, "COUNT")
                if "OPEN_QUESTIONS.md" in f["where"] and "registry total" in f["message"]]
        self.assertTrue(hits, "must fail on the registry total specifically")

    def test_59_stale_uncovered_count_fails(self):
        """NEGATIVE: 88 -> 78 fails, and names the not-implemented assertion,
        with the registry total left correct so the two cannot be confused."""
        n = entry_count(self.root)
        t = read(self._oq())
        after = t.replace("  %d uncovered entries" % (n - 19),
                          "  %d uncovered entries" % (n - 29), 1)
        self.assertNotEqual(t, after, "fixture drift: uncovered sentence")
        write(self._oq(), after)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        hits = [f for f in findings_of(out, "COUNT")
                if "OPEN_QUESTIONS.md" in f["where"] and "not-implemented" in f["message"]]
        self.assertTrue(hits, "must fail on the uncovered count specifically")
        totals = [f for f in findings_of(out, "COUNT")
                  if "OPEN_QUESTIONS.md" in f["where"] and "registry total" in f["message"]]
        self.assertEqual(totals, [], "must NOT also fire the total assertion")

    def test_60_stale_doctor_coverage_fails(self):
        """NEGATIVE: 19 -> 18 fails on the doctor-coverage half."""
        n = entry_count(self.root)
        t = read(self._oq())
        after = t.replace("**19 of %d** entries" % n, "**18 of %d** entries" % n, 1)
        self.assertNotEqual(t, after, "fixture drift")
        write(self._oq(), after)
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        hits = [f for f in findings_of(out, "COUNT")
                if "OPEN_QUESTIONS.md" in f["where"] and "doctor coverage" in f["message"]]
        self.assertTrue(hits, "must fail on doctor coverage specifically")

    def test_61_patterns_actually_match_a_known_string(self):
        """A guard whose regex silently matches nothing passes every tree.

        The first version of the uncovered-count pattern was written with a
        literal backspace byte instead of a word boundary, so it compiled,
        loaded and matched NOTHING. Zero inspected matches must not be able to
        look like a pass, so assert the patterns fire on a known string.
        """
        # Loaded from an absolute path derived from INTEGRITY, not from
        # sys.path. Running this file as `python3 -m unittest
        # integrity.tests.test_mutations` does not put integrity/ on the path,
        # and a bare import would raise ModuleNotFoundError, which is an ERROR
        # rather than this assertion failing. A guard test that cannot run is
        # the same defect class it exists to catch.
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "_ri_for_test", os.path.join(INTEGRITY, "registry_integrity.py"))
        ri = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(ri)
        total_line = "checks for **19 of 107** entries and"
        orphan_line = "  88 uncovered entries are reachable"
        self.assertTrue(
            any(rx.search(total_line) for rx, _t, _i in ri.TOTAL_PATTERNS),
            "no TOTAL pattern matches the bold-spanning coverage sentence")
        self.assertTrue(
            any(rx.search(orphan_line) for rx in ri.ORPHAN_PATTERNS),
            "no ORPHAN pattern matches the uncovered-entries sentence")

class ClaimLedgerMutations(unittest.TestCase):
    """The claim-propagation checks, including the requirement that made the
    whole thing enforceable."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="minefield-claims-")
        self.ledger_path = os.path.join(self.tmp, "claims.json")
        self.ledger = json.loads(read(os.path.join(INTEGRITY, "claims.json")))
        self.peer = peer_repo()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save(self):
        write(self.ledger_path, json.dumps(self.ledger, indent=2))
        return self.ledger_path

    def claim(self, cid):
        for c in self.ledger["claims"]:
            if c["id"] == cid:
                return c
        raise AssertionError("no claim %s" % cid)

    def test_20_retraction_without_search_terms_is_rejected(self):
        """THE requirement. A retraction with no recorded phrasings is not a
        retraction anyone can enforce, so the ledger refuses it."""
        self.claim("depth-dose-suppression")["search_phrasings"] = []
        rc, out = run_claims(self.save(), {})
        self.assertEqual(rc, 1)
        blob = json.dumps(out)
        self.assertIn("no search_phrasings recorded", blob)
        self.assertIn("depth-dose-suppression", blob)

    def test_21_phrasing_without_a_note_is_rejected(self):
        self.claim("cap-hits-are-failures")["search_phrasings"][0].pop("note")
        rc, out = run_claims(self.save(), {})
        self.assertEqual(rc, 1)
        self.assertIn("has no note", json.dumps(out))

    def test_22_retraction_without_correction_anchors_is_rejected(self):
        """Without anchors, any correction anywhere in the window vouches for
        the claim. That is how the Qwen dose-depth paragraph passed during
        bring-up: an unrelated PR-10 correction sat 30 lines below it."""
        self.claim("qwen-dose-depth-throttle").pop("correction_anchors")
        rc, out = run_claims(self.save(), {})
        self.assertEqual(rc, 1)
        self.assertIn("no correction_anchors", json.dumps(out))

    def test_23_retraction_without_superseded_by_is_rejected(self):
        self.claim("trap42-capability-reading").pop("superseded_by")
        rc, out = run_claims(self.save(), {})
        self.assertEqual(rc, 1)
        self.assertIn("no superseded_by", json.dumps(out))

    def test_24_retracted_phrasing_reintroduced_with_no_correction(self):
        """The failure that cost the most: the retracted wording survives in an
        advice section that carries no correction."""
        root = os.path.join(self.tmp, "fake")
        write(os.path.join(root, "OPERATORS.md"),
              "# Operator advice\n\n"
              "Keep the system prompt lean: every rule block you add shortens "
              "the reasoning you get even when it still fires.\n\n"
              "Unrelated paragraph with no bearing on any of this.\n")
        rc, out = run_claims(self.save(), {"laguna": root})
        self.assertEqual(rc, 1)
        flagged = [h for h in out["hits"] if h["verdict"] == "FLAGGED"]
        self.assertTrue(any(h["claim"] == "depth-dose-suppression"
                            and h["path"] == "OPERATORS.md" for h in flagged),
                        flagged)

    def test_25_same_phrasing_with_its_correction_is_not_flagged(self):
        """Negative control for 24. Without this, a checker that flagged
        everything would pass test 24 and be useless."""
        root = os.path.join(self.tmp, "fake2")
        write(os.path.join(root, "OPERATORS.md"),
              "# Operator advice\n\n"
              "Keep the system prompt lean: every rule block you add shortens "
              "the reasoning you get even when it still fires.\n\n"
              "**CORRECTION 2026-07-28: withdrawn. The in-run interleaved depth "
              "grid found all pairwise p >= 0.13; see c7-depth-collapse.**\n")
        rc, out = run_claims(self.save(), {"laguna": root})
        flagged = [h for h in out["hits"] if h["verdict"] == "FLAGGED"]
        self.assertEqual(flagged, [], flagged)
        self.assertTrue(any(h["verdict"] == "CONTEXT" for h in out["hits"]))

    def test_26_a_correction_about_something_else_does_not_vouch(self):
        """The bug this checker had, kept as a test. An unrelated correction in
        the window must not launder a surviving claim."""
        root = os.path.join(self.tmp, "fake3")
        body = ["# Findings", "",
                "Qwen's is a **throttle** (how long it thinks before "
                "answering).", ""]
        body += ["Filler line %d." % i for i in range(12)]
        body += ["**CORRECTION: the thinking-ON codegen claim does not survive "
                 "temperature control; the +2.64 was measured at two "
                 "temperatures.**", ""]
        write(os.path.join(root, "README.md"), "\n".join(body) + "\n")
        rc, out = run_claims(self.save(), {"laguna": root})
        self.assertEqual(rc, 1)
        flagged = [h for h in out["hits"] if h["verdict"] == "FLAGGED"]
        self.assertTrue(any(h["claim"] == "qwen-dose-depth-throttle"
                            for h in flagged), out["hits"])

    def test_27_exempt_path_is_reported_but_never_fatal(self):
        root = os.path.join(self.tmp, "fake4")
        write(os.path.join(root, "TWEET_PACK_V3.1.md"),
              "As posted: reasoning length collapses monotonically with dose.\n")
        rc, out = run_claims(self.save(), {"laguna": root})
        flagged = [h for h in out["hits"] if h["verdict"] == "FLAGGED"]
        self.assertEqual(flagged, [], flagged)
        self.assertTrue(any(h["verdict"] == "EXEMPT" for h in out["hits"]),
                        out["hits"])

    def test_28_a_deleted_surface_makes_the_ledger_stale(self):
        self.claim("cap-hits-are-failures")["carried_by"].append(
            {"surface": "minefield:traps/evaluation/99-gone.md",
             "state": "fixture"})
        rc, out = run_claims(self.save(), {"minefield": REPO})
        self.assertEqual(rc, 1)
        self.assertIn("carried_by surface does not exist",
                      json.dumps(out["ledger_errors"]))

    def test_30_a_nested_checkout_is_not_scanned_as_this_repo(self):
        """The bug that turned CI red on its first run.

        actions/checkout put the peer repo INSIDE the workspace. Every peer
        file was then scanned twice: once correctly as laguna:<path>, and once
        as minefield:.peer/laguna-s21-lab/<path>, a name no laguna: exemption
        matches. A correctly exempt line in gate-study/README.md came back
        FLAGGED and the whole run went red on a non-finding.

        Both halves are asserted: the nested copy must not be scanned under the
        outer repo's name, and the outer repo must still be scanned.
        """
        outer = os.path.join(self.tmp, "outer")
        write(os.path.join(outer, "OUTER.md"), "# Outer\n\nNothing to see.\n")
        nested = os.path.join(outer, ".peer", "laguna-s21-lab")
        os.makedirs(os.path.join(nested, ".git"))
        write(os.path.join(nested, "TWEET_PACK_V3.1.md"),
              "As posted: reasoning length collapses monotonically with dose.\n")

        rc, out = run_claims(self.save(), {"minefield": outer})
        paths = [h["path"] for h in out["hits"]]
        self.assertFalse(
            any(".peer" in p for p in paths),
            "a nested checkout of another repo was scanned under this repo's "
            "name: %s" % paths)
        self.assertEqual([h for h in out["hits"] if h["verdict"] == "FLAGGED"],
                         [], out["hits"])

    def test_31_pruning_does_not_silently_stop_scanning_everything(self):
        """Negative control for 30, and the false-healthy guard.

        The cheapest way to make test 30 pass is to scan nothing. This asserts
        the scanner still reads ordinary content in the same tree, so a prune
        that swallowed the whole walk would fail here.
        """
        outer = os.path.join(self.tmp, "outer2")
        write(os.path.join(outer, "TWEET_PACK_V3.1.md"),
              "As posted: reasoning length collapses monotonically with dose.\n")
        nested = os.path.join(outer, "vendor", "someone-else")
        os.makedirs(os.path.join(nested, ".git"))
        write(os.path.join(nested, "THEIRS.md"), "unrelated\n")

        rc, out = run_claims(self.save(), {"laguna": outer})
        self.assertTrue(
            any(h["path"] == "TWEET_PACK_V3.1.md" for h in out["hits"]),
            "pruning nested repos also stopped the scanner reading the repo "
            "it was pointed at: %s" % out["hits"])

    def test_32_flagged_hits_emit_a_github_annotation(self):
        """A red badge has to say what and where. The first red run's only
        annotation was 'Process completed with exit code 1'."""
        root = os.path.join(self.tmp, "annot")
        write(os.path.join(root, "OPERATORS.md"),
              "# Operator advice\n\n"
              "Keep the system prompt lean: every rule block you add shortens "
              "the reasoning you get even when it still fires.\n")
        r = subprocess.run(
            [PY, os.path.join(INTEGRITY, "claim_propagation.py"),
             "--ledger", self.save(), "--github", "--repo", "laguna=%s" % root],
            capture_output=True, text=True, cwd=root)
        self.assertEqual(r.returncode, 1)
        lines = [l for l in r.stdout.splitlines() if l.startswith("::error")]
        self.assertTrue(lines, r.stdout)
        self.assertTrue(any("file=OPERATORS.md" in l for l in lines), lines)
        self.assertTrue(any("depth-dose-suppression" in l for l in lines), lines)

    def test_29_live_tree_scan_runs_and_is_reported(self):
        """Not an assertion that the live tree is clean. It asserts the scan
        actually reaches both repos and produces classified hits, so a run that
        silently scanned nothing cannot look like a pass."""
        if not self.peer:
            self.skipTest("peer repo not found; set MINEFIELD_PEER_REPO")
        rc, out = run_claims(os.path.join(INTEGRITY, "claims.json"),
                             {"minefield": REPO, "laguna": self.peer})
        self.assertTrue(out["hits"], "scan produced no hits at all, which means "
                                     "it did not read the trees")
        repos_seen = {h["repo"] for h in out["hits"]}
        self.assertIn("laguna", repos_seen)

    def test_33_a_bare_run_cannot_report_clean_over_nothing(self):
        """The footgun this pair exists for. With no --repo the tool built an
        empty repo map, every loop in scan() ran zero times, nothing was
        FLAGGED, and it printed PASS and exited 0. CI always passed --repo, so
        only a human or an agent running it plainly got the false clean, on
        the one tool built to prevent false cleans."""
        r = subprocess.run(
            [PY, os.path.join(INTEGRITY, "claim_propagation.py"),
             "--ledger", os.path.join(INTEGRITY, "claims.json")],
            capture_output=True, text=True, cwd=REPO)
        # It must say what it scanned, and the count must not be zero.
        self.assertIn("SCANNED:", r.stdout, r.stdout[-800:])
        self.assertNotIn("SCANNED: minefield=0 files", r.stdout)
        # And it must have announced the default rather than applying it
        # silently.
        self.assertIn("no --repo given", r.stdout)
        # A PASS is only acceptable here because it scanned the live tree.
        if "PASS" in r.stdout:
            self.assertEqual(r.returncode, 0)

    def test_34_a_repo_holding_no_files_is_exit_3_not_pass(self):
        """The general form: the guard is on what was actually opened, not on
        whether --repo was typed. A path that exists but holds nothing
        scannable is the same empty comparison set."""
        empty = os.path.join(self.tmp, "empty-repo")
        os.makedirs(empty)
        r = subprocess.run(
            [PY, os.path.join(INTEGRITY, "claim_propagation.py"),
             "--ledger", self.save(), "--repo", "minefield=%s" % empty],
            capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 3, r.stdout[-800:])
        self.assertIn("REFUSING TO REPORT CLEAN", r.stdout)
        self.assertNotIn("PASS:", r.stdout)

    def test_35_an_empty_peer_does_not_hide_behind_a_good_repo(self):
        """A real repo plus an unreachable peer must not read as clean. This
        is the shape a missing peer checkout actually takes on a laptop."""
        empty = os.path.join(self.tmp, "empty-peer")
        os.makedirs(empty)
        r = subprocess.run(
            [PY, os.path.join(INTEGRITY, "claim_propagation.py"),
             "--ledger", self.save(),
             "--repo", "minefield=%s" % REPO,
             "--repo", "laguna=%s" % empty],
            capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 3, r.stdout[-800:])
        self.assertIn("laguna", r.stdout)
        self.assertNotIn("PASS:", r.stdout)

    def test_36_the_guard_does_not_swallow_a_real_flagged_hit(self):
        """The negative control for the guard itself. A guard that turned every
        run into exit 3 would also stop reporting real findings, so this plants
        a retracted phrasing with no correction and asserts the ordinary FAIL
        still comes through."""
        root = os.path.join(self.tmp, "planted")
        write(os.path.join(root, "OPERATORS.md"),
              "# Operator advice\n\n"
              "Keep the system prompt lean: every rule block you add shortens "
              "the reasoning you get even when it still fires.\n")
        r = subprocess.run(
            [PY, os.path.join(INTEGRITY, "claim_propagation.py"),
             "--ledger", self.save(), "--repo", "laguna=%s" % root],
            capture_output=True, text=True, cwd=root)
        self.assertEqual(r.returncode, 1, r.stdout[-800:])
        self.assertIn("FAIL:", r.stdout)
        self.assertNotIn("REFUSING TO REPORT CLEAN", r.stdout)


class DoNotCiteMutations(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="minefield-dnc-")
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(self.root)
        for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "t"]):
            subprocess.run(["git"] + cmd, cwd=self.root, capture_output=True)
        write(os.path.join(self.root, "NOTES.md"), "# Notes\n\nBaseline.\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root,
                       capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dnc(self, *extra):
        r = subprocess.run([PY, os.path.join(INTEGRITY, "do_not_cite.py"),
                            "--list", os.path.join(INTEGRITY, "do_not_cite.json"),
                            "--root", self.root, "--json"] + list(extra),
                           capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def test_40_banned_figure_in_added_text(self):
        write(os.path.join(self.root, "NOTES.md"),
              "# Notes\n\nBaseline.\n\nWe measured Spark 19.44 tok/s.\n")
        rc, out = self.dnc("--base", "HEAD")
        self.assertEqual(rc, 1)
        self.assertTrue(any(h["id"] == "stevibe-cross-hardware"
                            for h in out["hits"]), out)

    def test_41_banned_phrasing_in_added_text(self):
        write(os.path.join(self.root, "NOTES.md"),
              "# Notes\n\nBaseline.\n\nThis profile beats r0b0tlab on decode.\n")
        rc, out = self.dnc("--base", "HEAD")
        self.assertEqual(rc, 1)
        self.assertTrue(any(h["id"] == "beat-r0b0tlab" for h in out["hits"]), out)
        self.assertTrue(out["hits"][0]["instead"])

    def test_42_unchanged_tree_is_clean(self):
        """Negative control: the check must be silent when nothing was added."""
        rc, out = self.dnc("--base", "HEAD")
        self.assertEqual(rc, 0)
        self.assertEqual(out["hits"], [])

    def test_43_pre_existing_text_is_not_flagged(self):
        """Scope control: the list is about what you are publishing now. A
        banned string already in the baseline is not an added-text violation,
        or every commit fails forever and the check gets turned off."""
        write(os.path.join(self.root, "NOTES.md"),
              "# Notes\n\nBaseline.\n\nWe measured Spark 19.44 tok/s.\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "pre-existing"], cwd=self.root,
                       capture_output=True)
        write(os.path.join(self.root, "NOTES.md"),
              "# Notes\n\nBaseline.\n\nWe measured Spark 19.44 tok/s.\n\n"
              "An ordinary new sentence.\n")
        rc, out = self.dnc("--base", "HEAD")
        self.assertEqual(rc, 0, out)

    def test_44_exempt_path_is_reported_not_failed(self):
        write(os.path.join(self.root, "SOURCE_ARCHIVES_NOTES.md"),
              "NOT LOCATED: the Spark 19.44 / PRO6000 108 post.\n")
        rc, out = self.dnc("--base", "HEAD")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["exempt"], out)

    def test_45_a_brand_new_untracked_file_is_scanned(self):
        """git diff does not show an untracked file. A new writeup is entirely
        added text and is the likeliest place for a fresh citation, so it has
        to be read directly."""
        write(os.path.join(self.root, "NEW_WRITEUP.md"),
              "# New writeup\n\nOur profile beats r0b0tlab.\n")
        rc, out = self.dnc("--base", "HEAD")
        self.assertEqual(rc, 1, out)
        self.assertTrue(any(h["path"] == "NEW_WRITEUP.md" for h in out["hits"]),
                        out)



if __name__ == "__main__":
    unittest.main(verbosity=2)
