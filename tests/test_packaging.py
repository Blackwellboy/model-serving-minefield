"""What the wheel ships and when it is published.

An installed user has no repository: the registry, the leads catalog and the
doctor copy must travel as package data, or the installed CLI falls back to
paths that do not exist. The release workflow builds the wheel and smoke-tests
it outside the checkout; these tests catch the cheaper mistakes first.
"""

from __future__ import annotations

import fnmatch
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(sys.version_info < (3, 11), "tomllib needs Python 3.11")
class PackageData(unittest.TestCase):
    def setUp(self):
        import tomllib

        self.project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_every_data_file_matches_a_package_data_glob(self):
        globs = self.project["tool"]["setuptools"]["package-data"]["minefield"]
        data = ROOT / "minefield" / "data"
        files = [p.relative_to(ROOT / "minefield").as_posix() for p in data.iterdir() if p.is_file()]
        self.assertTrue(files)
        dropped = [f for f in files if not any(fnmatch.fnmatch(f, g) for g in globs)]
        self.assertEqual(dropped, [], "these would be left out of the wheel")

    def test_files_the_installed_package_loads_are_shipped(self):
        for name in ("MINEFIELD_REGISTRY.json", "UNVERIFIED_LEADS.json", "minefield_doctor.py"):
            self.assertTrue((ROOT / "minefield" / "data" / name).is_file(), name)

    def test_pypi_description_has_no_relative_links(self):
        text = (ROOT / self.project["project"]["readme"]).read_text(encoding="utf-8")
        relative = [t for t in re.findall(r"\]\(([^)]+)\)", text) if not t.startswith("https://")]
        self.assertEqual(relative, [], "PyPI cannot resolve repository-relative links")


class ReleaseWorkflow(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    def test_runs_only_on_a_version_tag(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\njobs:\n", 1)[0]
        self.assertIn('tags: ["v*"]', trigger)
        for other in ("pull_request", "branches", "workflow_dispatch", "schedule"):
            self.assertNotIn(other, trigger)

    def test_publishes_by_trusted_publishing_not_a_stored_token(self):
        publish = self.text.split("\n  publish-pypi:\n", 1)[1]
        self.assertIn("id-token: write", publish)
        self.assertIn("name: pypi", publish)
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("password:", self.text)


if __name__ == "__main__":
    unittest.main()
