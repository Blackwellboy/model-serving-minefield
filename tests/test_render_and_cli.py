"""Human-readable output and the `minefield <symptom>` shorthand."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from minefield.matching import diagnose
from minefield.registry import load_registry
from minefield.render import render_diagnosis

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = load_registry()


def _cli(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "minefield", *args],
        capture_output=True, text=True, env=env, cwd=ROOT, check=False,
    )


class RenderTests(unittest.TestCase):
    def test_strong_match_shows_check_and_clickable_link(self):
        text = render_diagnosis(
            diagnose(REGISTRY, "streaming shows blank replies", stack="vllm"),
            stream=io.StringIO(),
        )
        self.assertIn("Trap 23", text)
        self.assertIn("strong match", text)
        self.assertIn("check:", text)
        url = [line for line in text.splitlines() if "read:" in line][0]
        self.assertIn("traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md", url)
        self.assertIn("Next step:", text)

    def test_miss_says_not_documented_never_safe(self):
        text = render_diagnosis(diagnose(REGISTRY, "how do I bake bread"), stream=io.StringIO())
        self.assertIn("No documented trap matches", text)
        self.assertIn("not that your setup is safe", text)
        self.assertNotIn("Unverified leads", text)

    def test_no_color_codes_when_not_a_terminal(self):
        text = render_diagnosis(diagnose(REGISTRY, "empty content at token ceiling"), stream=io.StringIO())
        self.assertNotIn("\033[", text)

    def test_output_is_short(self):
        text = render_diagnosis(diagnose(REGISTRY, "empty content at token ceiling"), stream=io.StringIO())
        self.assertLess(len(text.splitlines()), 40)


class CliTests(unittest.TestCase):
    def test_piped_output_stays_json_for_scripts_and_agents(self):
        result = _cli("guide", "streaming shows blank replies")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("matches", json.loads(result.stdout))

    def test_bare_symptom_shorthand_and_text_flag(self):
        result = _cli("--text", "stopped", "the", "container", "but", "the", "next", "model", "fails", "with", "out", "of", "memory")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Trap 81", result.stdout)

    def test_known_commands_are_not_treated_as_symptoms(self):
        result = _cli("coverage", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("total_canonical_traps", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
