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
        p = os.path.join(self.root, "doctor", "minefield_doctor.py")
        write(p, read(p).replace("REGISTRY_TRAP_COUNT = 42",
                                 "REGISTRY_TRAP_COUNT = 41"))
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        counts = findings_of(out, "COUNT")
        self.assertTrue(any("minefield_doctor.py" in f["where"] for f in counts))
        self.assertTrue(any("declares registry total 41" in f["message"]
                            and "tree has 42" in f["message"] for f in counts),
                        counts)

    def test_03_stale_count_in_a_launch_document(self):
        """The stale-count failure, prose side: a new entry lands and the
        README coverage sentence keeps the old total."""
        write(os.path.join(self.root, "traps", "routing",
                           "43-a-new-entry-for-the-mutation-test.md"),
              "# Trap 43: fixture\n\n**Found by Blackwellboy.**\n\n"
              "**Status: reproduced here** (fixture).\n")
        rc, out = run_registry(self.root)
        self.assertEqual(rc, 1)
        counts = findings_of(out, "COUNT")
        wheres = " ".join(f["where"] for f in counts)
        self.assertIn("README.md", wheres)
        self.assertIn("doctor/README.md", wheres)
        self.assertIn("doctor/minefield_doctor.py", wheres)
        self.assertTrue(any("tree has 43 entries" in f["message"] for f in counts))

    def test_04_redirect_stubs_are_counted_as_entries(self):
        """The counting rule itself. If the seven flat stubs were ever counted
        as entries the total would read 49 and every count check would invert.
        This asserts the tool's own arithmetic, which is the thing all the
        other count assertions rest on."""
        rc, out = run_registry(self.root)
        self.assertEqual(out["entries"], 42)
        self.assertEqual(out["stubs"], 7)

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
