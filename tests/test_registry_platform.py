import io
import json
import tempfile
import unittest
from pathlib import Path

from minefield.coverage import build_coverage
from minefield.generator import _portable_bytes, build
from minefield.mcp_server import TOOLS, call_tool, serve
from minefield.registry import (
    ROOT, RegistryError, _load_overrides, _status_labels, canonical_paths,
    compile_registry,
)


class RegistryPlatformTests(unittest.TestCase):
    def test_pack_text_bytes_are_platform_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.md"
            path.write_bytes(b"one\r\ntwo\rthree\n")
            self.assertEqual(_portable_bytes(path), b"one\ntwo\nthree\n")

    @classmethod
    def setUpClass(cls):
        cls.registry = compile_registry()

    def test_canonical_registry_is_complete_and_unique(self):
        paths = canonical_paths()
        self.assertEqual(len(paths), self.registry["canonical_trap_count"])
        ids = [entry["id"] for entry in self.registry["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("traps/01-reasoning-field-two-names.md",
                         [entry["source_path"] for entry in self.registry["entries"]])
        for entry in self.registry["entries"]:
            self.assertTrue((ROOT / entry["source_path"]).is_file())
            self.assertTrue(entry["symptom"])
            self.assertTrue(entry["check"])
            self.assertTrue(entry["evidence_strength"])

    def test_doctor_coverage_is_derived(self):
        mapped = [entry for entry in self.registry["entries"]
                  if entry["doctor_coverage"]["implemented"]]
        self.assertEqual(len(mapped), self.registry["doctor_implemented_trap_count"])
        self.assertEqual(19, len(mapped))

    def test_coverage_declares_every_modality_for_every_trap(self):
        coverage = build_coverage(self.registry)
        self.assertEqual(self.registry["canonical_trap_count"], len(coverage["traps"]))
        expected = {"endpoint_probe", "static_config", "log_scan",
                    "guided_experiment", "human_review"}
        for item in coverage["traps"]:
            self.assertEqual(expected, set(item["modalities"]))
        self.assertTrue(coverage["summary"]["counts_overlap"])

    def test_generation_is_byte_deterministic(self):
        first = build()
        snapshots = {path.name: path.read_bytes() for path in (ROOT / "dist").iterdir()
                     if path.is_file()}
        second = build()
        self.assertEqual(first, second)
        self.assertEqual(snapshots, {path.name: path.read_bytes()
                                    for path in (ROOT / "dist").iterdir()
                                    if path.is_file()})
        bundle = (ROOT / "dist" / "MINEFIELD_AGENT_BUNDLE.md").read_text(encoding="utf-8")
        for entry in self.registry["entries"]:
            self.assertIn(f"### Trap {entry['id']}:", bundle)

    def test_mcp_tools_are_read_only_and_callable(self):
        self.assertEqual(10, len(TOOLS))
        self.assertNotIn("shell", " ".join(TOOLS).lower())
        found = call_tool("get_trap", {"id": "01"}, self.registry)
        self.assertEqual("01", found["id"])
        source = io.StringIO(
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        )
        output = io.StringIO()
        self.assertEqual(0, serve(source, output))
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual("model-serving-minefield", lines[0]["result"]["serverInfo"]["name"])
        self.assertEqual(10, len(lines[1]["result"]["tools"]))
        malformed_in = io.StringIO("{not-json}\n")
        malformed_out = io.StringIO()
        serve(malformed_in, malformed_out)
        self.assertIn("error", json.loads(malformed_out.getvalue()))

    def test_generated_registry_matches_declared_schema_contract(self):
        schema = json.loads((ROOT / "registry" / "schema.json").read_text(encoding="utf-8"))
        self.assertEqual("object", schema["type"])
        self.assertEqual(set(schema["required"]),
                         set(key for key in schema["required"] if key in self.registry))
        required_entry = set(schema["properties"]["entries"]["items"]["required"])
        for entry in self.registry["entries"]:
            self.assertTrue(required_entry <= set(entry))


class RegistryMutationTests(unittest.TestCase):
    def test_duplicate_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "traps" / "a").mkdir(parents=True)
            (root / "traps" / "b").mkdir(parents=True)
            (root / "traps" / "a" / "01-a.md").write_text("", encoding="utf-8")
            (root / "traps" / "b" / "01-b.md").write_text("", encoding="utf-8")
            with self.assertRaises(RegistryError):
                canonical_paths(root)

    def test_malformed_override_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "registry").mkdir(parents=True)
            (root / "registry" / "overrides.json").write_text("[", encoding="utf-8")
            with self.assertRaises(RegistryError):
                _load_overrides(root)

    def test_evidence_upgrade_and_identity_override_are_rejected(self):
        with self.assertRaises(RegistryError):
            _status_labels("universally proven")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "registry").mkdir(parents=True)
            (root / "registry" / "overrides.json").write_text(
                '{"01":{"status":"reproduced here"}}', encoding="utf-8"
            )
            with self.assertRaises(RegistryError):
                _load_overrides(root)


if __name__ == "__main__":
    unittest.main()
