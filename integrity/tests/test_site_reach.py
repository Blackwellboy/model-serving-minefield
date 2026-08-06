#!/usr/bin/env python3
"""Regression guard: the claim ledger must keep REACHING the Pages site.

The site is a single index.html. claim_propagation scanned only .md and .txt,
so pointing it at that repo returned a confident CLEAN having read nothing but
the README. That is a false CLEAN on the most public surface we own, and it is
how the site carried a retracted depth claim for a day after three other
surfaces were corrected.

These tests fail if someone reverts the extension list or drops the
site-shaped phrasings, either of which would silently restore the blind spot.
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INTEGRITY = os.path.dirname(HERE)
ROOT = os.path.dirname(INTEGRITY)
sys.path.insert(0, INTEGRITY)

import claim_propagation as cp


class SiteReach(unittest.TestCase):
    def test_html_is_scanned(self):
        self.assertIn(".html", cp.SCAN_EXTS,
                      "dropping .html makes the Pages site invisible to the "
                      "ledger and any run against it a false CLEAN")

    def test_site_registered_as_a_repo(self):
        ledger = json.load(open(os.path.join(INTEGRITY, "claims.json"),
                                encoding="utf-8"))
        self.assertIn("bbio", ledger["repos"],
                      "the Pages site must stay a declared surface")

    def test_depth_claim_has_site_shaped_phrasings(self):
        """The markdown-shaped phrasings do not match how the site said it.
        At least one phrasing must match the site's own wording."""
        ledger = json.load(open(os.path.join(INTEGRITY, "claims.json"),
                                encoding="utf-8"))
        claim = next(c for c in ledger["claims"]
                     if c["id"] == "depth-dose-suppression")
        pats = [p["pattern"] for p in claim["search_phrasings"]]
        site_sentence = ("under the heaviest agent prompt, and I read that as "
                         "prompt dose shortening reasoning.")
        import re
        self.assertTrue(
            any(re.search(p, site_sentence, re.I) for p in pats),
            "no registered phrasing matches the sentence the site actually "
            "used; the ledger would not have caught it")

    def test_a_synthetic_uncorrected_site_page_is_flagged(self):
        """End to end: an HTML page carrying the retracted wording with no
        correction near it must FLAG, not pass."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "site"))
            with open(os.path.join(d, "site", "index.html"), "w",
                      encoding="utf-8") as fh:
                fh.write("<html><body><p>I read that as prompt dose "
                         "shortening reasoning.</p></body></html>\n")
            ledger = cp.load_ledger(os.path.join(INTEGRITY, "claims.json")) \
                if hasattr(cp, "load_ledger") else None
            rc = cp.main_for_test(d) if hasattr(cp, "main_for_test") else None
            if rc is None:
                import subprocess
                p = subprocess.run(
                    [sys.executable, os.path.join(INTEGRITY,
                                                  "claim_propagation.py"),
                     "--repo", "bbio=%s" % os.path.join(d, "site")],
                    capture_output=True, text=True)
                self.assertEqual(p.returncode, 1,
                                 "uncorrected site wording must flag:\n"
                                 + p.stdout + p.stderr)
                self.assertIn("FLAGGED", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
