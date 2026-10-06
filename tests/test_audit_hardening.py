"""Regression tests for the security and malformed-input findings from audit."""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from minefield.mcp_server import call_tool
from minefield.model_inspector import inspect_model_folder
from minefield.registry import load_registry
from minefield.results_inspector import inspect_results
from minefield.scan import scan


class AuditHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def model(self, relative: str = "model") -> Path:
        folder = self.root / relative
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "config.json").write_text(
            json.dumps({"model_type": "llama", "max_position_embeddings": 8192}),
            encoding="utf-8",
        )
        (folder / "generation_config.json").write_text("{}", encoding="utf-8")
        return folder

    def test_mcp_scan_does_not_read_cache_refs_above_allowed_root(self) -> None:
        cache = self.root / "models--org--model"
        snapshot = cache / "snapshots" / "abc"
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").write_text(
            json.dumps({"model_type": "llama"}), encoding="utf-8"
        )
        (snapshot / "generation_config.json").write_text("{}", encoding="utf-8")
        (cache / "refs").mkdir(parents=True)
        (cache / "refs" / "main").write_text("bad-ref\n", encoding="utf-8")

        report = call_tool(
            "scan_files",
            {"paths": [str(snapshot)]},
            load_registry(),
            allowed_roots=[str(snapshot)],
        )
        self.assertNotIn("131", report["traps"], report)

        # The same cache root is intentionally visible when it itself is allowed.
        direct = inspect_model_folder(snapshot, allowed_roots=[str(cache)])
        self.assertIn("131", {item["trap_id"] for item in direct["findings"]})

    def test_single_token_stack_lookup_uses_declared_context(self) -> None:
        matches = call_tool(
            "get_stack_checks", {"stack": "vllm"}, load_registry()
        )
        self.assertTrue(matches)
        self.assertTrue(all(item["match_type"] == "declared-context-only" for item in matches))
        self.assertTrue(any("vllm" in item["matched_context"].lower() for item in matches))

    def test_single_token_model_lookup_uses_declared_context(self) -> None:
        report = call_tool(
            "get_model_risks", {"model": "Qwen"}, load_registry()
        )
        self.assertTrue(report["matches"])
        self.assertTrue(any(
            "qwen" in item["matched_context"].lower()
            for item in report["matches"]
        ))
        self.assertIn("not diagnoses", report["warning"])

    def test_scalar_json_is_rejected_without_a_type_error(self) -> None:
        path = self.write("scalar.json", "42")
        with self.assertRaisesRegex(ValueError, "must be an object"):
            inspect_results(path)
        report = scan([str(path)])
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("not parsed as eval results" in note for note in report["notes"]), report)

    def test_malformed_openai_envelopes_do_not_crash(self) -> None:
        path = self.write("bad-envelope.json", json.dumps({
            "results": [
                {"response": {"choices": ["not-an-object"]}},
                {"response": {"choices": [{
                    "finish_reason": "stop", "message": "not-an-object",
                }]}, "score": 0},
            ]
        }))
        report = inspect_results(path)
        self.assertEqual(report["records"], 2)
        self.assertIsInstance(report["findings"], list)

    def test_malformed_quantization_config_is_bounded(self) -> None:
        folder = self.root / "Qwen-NVFP4"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps({
            "model_type": "qwen3_next",
            "quantization_config": ["not", "an", "object"],
        }), encoding="utf-8")
        report = inspect_model_folder(folder)
        self.assertIn("10", {item["trap_id"] for item in report["findings"]})
        self.assertTrue(any("not an object" in note for note in report["notes"]), report)

    @unittest.skipUnless(os.name == "posix", "hard memory isolation is POSIX-only")
    def test_recursive_scan_survives_a_single_operation_memory_bomb(self) -> None:
        folder = self.model("bomb")
        (folder / "chat_template.jinja").write_text(
            '{{ "x" * 1000000000 }}', encoding="utf-8"
        )
        started = time.monotonic()
        report = scan([str(folder)])
        self.assertLess(time.monotonic() - started, 20.0)
        joined = "\n".join(report["notes"])
        self.assertRegex(joined, r"MemoryError|not checked|not a clean result|memory limit")

    def test_global_file_limit_applies_across_multiple_roots(self) -> None:
        for directory in ("a", "b"):
            for number in range(3):
                self.write(f"{directory}/launch-{number}.sh", "echo ok\n")
        with mock.patch("minefield.scan.MAX_FILES", 2):
            report = scan([str(self.root / "a"), str(self.root / "b")])
        self.assertLessEqual(len(report["scanned"]), 2, report["scanned"])
        self.assertTrue(any("global 2-file limit" in note for note in report["notes"]), report)

    def test_files_beside_model_metadata_still_reach_their_detectors(self) -> None:
        folder = self.model("deploy")
        self.write("deploy/server.log", "Killed\nexit code 137\n")
        self.write("deploy/merges.txt", "#version: 0.2\nt h\n")
        self.write("deploy/special_tokens_map.json", "{}")
        report = scan([str(folder)])
        kinds = {(Path(item["path"]).name, item["kind"]) for item in report["scanned"]}
        self.assertIn(("server.log", "log"), kinds, report["scanned"])
        self.assertIn(("deploy", "model folder"), kinds, report["scanned"])
        # Tokenizer files are model metadata, not configs or logs.
        names = {name for name, _ in kinds}
        self.assertNotIn("merges.txt", names, report["scanned"])
        self.assertNotIn("special_tokens_map.json", names, report["scanned"])

    def test_model_folder_reads_count_toward_the_global_byte_budget(self) -> None:
        self.model("a")
        self.model("b")
        with mock.patch("minefield.scan.MAX_TOTAL_BYTES", 100):
            report = scan([str(self.root)])
        folders = [item for item in report["scanned"] if item["kind"] == "model folder"]
        self.assertEqual(len(folders), 1, report["scanned"])
        self.assertTrue(any("model folder skipped" in note for note in report["notes"]), report)

    def test_isolated_template_does_not_read_sidecar_outside_allowed_roots(self) -> None:
        folder = self.root / "tpl"
        folder.mkdir()
        (folder / "tokenizer_config.json").write_text(
            json.dumps({"bos_token": "SIDECAR-SECRET"}), encoding="utf-8"
        )
        template = folder / "chat_template.jinja"
        template.write_text(
            "{{ bos_token }}{% for m in messages %}{{ m['content'] }}{% endfor %}",
            encoding="utf-8",
        )
        from minefield.template_inspector import load_template

        self.assertEqual(load_template(template, [str(template)])["bos_token"], "")
        self.assertEqual(load_template(template)["bos_token"], "SIDECAR-SECRET")
        report = call_tool(
            "scan_files", {"paths": [str(template)]}, load_registry(),
            allowed_roots=[str(template)],
        )
        self.assertNotIn("SIDECAR-SECRET", json.dumps(report))

    def test_scan_with_no_readable_path_exits_nonzero(self) -> None:
        from minefield.cli import main

        with mock.patch("sys.stdout"):
            self.assertEqual(main(["scan", "--json", str(self.root / "missing.sh")]), 2)
            self.write("ok.sh", "echo ok\n")
            self.assertIn(main(["scan", "--json", str(self.root / "ok.sh")]), (0, None))


if __name__ == "__main__":
    unittest.main()
