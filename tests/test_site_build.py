"""The Pages site builder writes one page per canonical trap and nothing else
that a reader would mistake for an entry."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

import build_site  # noqa: E402


class SiteBuildTests(unittest.TestCase):
    def test_one_page_per_trap_with_a_canonical_link(self):
        registry = json.loads((ROOT / "dist" / "MINEFIELD_REGISTRY.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            n = build_site.build(out, "https://example.invalid/msm")
            self.assertEqual(n, len(registry["entries"]))
            pages = sorted(p.parent.name for p in (out / "trap").glob("*/index.html"))
            self.assertEqual(pages, sorted(e["id"] for e in registry["entries"]))
            for entry in registry["entries"][:5] + registry["entries"][-3:]:
                text = (out / "trap" / entry["id"] / "index.html").read_text(encoding="utf-8")
                self.assertIn(entry["source_path"], text)
                self.assertIn("canonical entry", text)
            self.assertTrue((out / "index.html").exists())
            self.assertIn("https://example.invalid/msm/trap/", (out / "sitemap.xml").read_text(encoding="utf-8"))

    def test_page_text_is_escaped(self):
        entry = {"id": "99", "title": "<script>x</script>", "status": "under test.",
                 "symptom": "a < b", "category": "runtime", "contributor": "someone",
                 "source_path": "traps/runtime/99-x.md", "related_traps": []}
        page = build_site.trap_page(entry, "https://example.invalid")
        self.assertNotIn("<script>x</script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
