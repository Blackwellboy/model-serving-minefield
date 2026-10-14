"""The numbered menu: one catalogue for people, harnesses, MCP and harness plugins."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from minefield import menu
from minefield.cli import _command_names, parser
from minefield.mcp_server import call_tool
from minefield.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = {"symptom": "empty content after a tool call", "paths": ["a.yaml", "b.log"],
          "base_url": "http://127.0.0.1:9/v1", "model": "demo", "configs": ["c.yaml"],
          "logs": ["d.log", "e.log"]}


def _cli(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-m", "minefield", *args], input=stdin,
                          capture_output=True, text=True, env=env, cwd=ROOT, check=False)


class CatalogueTests(unittest.TestCase):
    def test_keys_and_ids_are_unique_and_numbered_in_order(self):
        keys = [i.key for i in menu.items()]
        self.assertEqual(keys, [str(n) for n in range(1, len(keys) + 1)])
        self.assertEqual(len({i.id for i in menu.items()}), len(keys))

    def test_every_item_says_what_it_touches(self):
        for item in menu.items():
            self.assertTrue(item.touches == "nothing" or item.touches == "files you name"
                            or item.touches.startswith("endpoint: up to "), item.id)

    def test_live_items_beyond_lite_ask_first(self):
        for item in menu.items():
            if item.touches.startswith("endpoint") and item.id != "lite":
                self.assertTrue(item.confirm, item.id)

    def test_every_item_builds_argv_the_real_cli_accepts(self):
        names = _command_names()
        for item in menu.items():
            argv = menu.build_argv(item, SAMPLE)
            if argv[0] == "quick":           # forwarded verbatim to the Doctor's own parser
                self.assertIn("--base-url", argv)
                continue
            self.assertIn(argv[0], names, item.id)
            parser().parse_args(argv)        # raises SystemExit on drift

    def test_flag_per_value_expansion_and_empty_lists(self):
        bundle = menu.find("bundle")
        self.assertEqual(menu.build_argv(bundle, {"configs": ["c.yaml"], "logs": ["d.log", "e.log"]}),
                         ["bundle", "--no-write", "--config", "c.yaml", "--log", "d.log", "--log", "e.log"])
        self.assertEqual(menu.build_argv(bundle, {}), ["bundle", "--no-write"])

    def test_optional_model_is_added_only_when_given(self):
        doctor = menu.find("doctor")
        self.assertNotIn("--model", menu.build_argv(doctor, {"base_url": "http://x/v1"}))
        self.assertEqual(menu.build_argv(doctor, {"base_url": "http://x/v1", "model": "m"})[-2:],
                         ["--model", "m"])

    def test_find_by_number_id_and_unique_prefix(self):
        self.assertEqual(menu.find("5").id, "doctor")
        self.assertEqual(menu.find("scan").id, "scan")
        self.assertEqual(menu.find("doc").id, "doctor")
        self.assertIsNone(menu.find("zzz"))
        self.assertIsNone(menu.find(""))

    def test_json_catalogue_is_versioned(self):
        data = menu.as_dict()
        self.assertEqual(data["schema"], menu.MENU_SCHEMA_VERSION)
        self.assertEqual(len(data["items"]), len(menu.items()))
        json.dumps(data)


class InteractiveTests(unittest.TestCase):
    def _run(self, typed: str):
        calls = []
        out = io.StringIO()
        code = menu.interactive(lambda argv: calls.append(list(argv)) or 0,
                                stdin=io.StringIO(typed), stdout=out)
        return code, calls, out.getvalue()

    def test_offline_choice_runs_without_asking(self):
        code, calls, out = self._run("1\nstreaming shows blank replies\n")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [["guide", "--text", "streaming shows blank replies"]])
        self.assertIn("Touches: nothing", out)

    def test_doctor_needs_a_yes_and_no_sends_nothing(self):
        code, calls, out = self._run("5\nhttp://127.0.0.1:9/v1\n\nn\n")
        self.assertEqual((code, calls), (0, []))
        self.assertIn("Nothing was sent", out)
        code, calls, _ = self._run("5\nhttp://127.0.0.1:9/v1\n\ny\n")
        self.assertEqual(calls, [["quick", "--base-url", "http://127.0.0.1:9/v1"]])

    def test_missing_required_input_stops(self):
        code, calls, out = self._run("3\n\n")
        self.assertEqual((code, calls), (2, []))
        self.assertIn("base_url is needed", out)

    def test_bad_choice_then_quit_and_eof(self):
        code, calls, out = self._run("42\nq\n")
        self.assertEqual((code, calls), (0, []))
        self.assertIn("Not an option", out)
        self.assertEqual(self._run("")[:2], (0, []))


class SurfaceTests(unittest.TestCase):
    def test_bare_minefield_prints_the_menu_when_not_a_terminal(self):
        res = _cli()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Model Serving Minefield", res.stdout)
        self.assertIn("Full Doctor on my endpoint", res.stdout)

    def test_menu_json_and_menu_is_not_a_symptom(self):
        res = _cli("menu", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["schema"], menu.MENU_SCHEMA_VERSION)
        self.assertIn("menu", _command_names())

    def test_mcp_lists_the_same_menu(self):
        self.assertEqual(call_tool("list_menu", {}, load_registry()), menu.as_dict())


if __name__ == "__main__":
    unittest.main()
