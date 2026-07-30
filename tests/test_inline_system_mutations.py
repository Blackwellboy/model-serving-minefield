import importlib.util
import tempfile
import unittest
from pathlib import Path

import minefield.inline_system as baseline

from tests.test_inline_system import fixture


class InlineSystemMutationTests(unittest.TestCase):
    def _load_mutant(self, old: str, new: str):
        source = Path(baseline.__file__).read_text(encoding="utf-8")
        self.assertIn(old, source)
        source = source.replace(old, new, 1)
        folder = tempfile.TemporaryDirectory()
        path = Path(folder.name) / "mutant.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("mutant_inline_system", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.addCleanup(folder.cleanup)
        return module

    def test_kills_dropped_without_negative_control_mutant(self):
        mutant = self._load_mutant("if matches_control:", "if True:")
        result = mutant.classify_manifest(fixture("<u>Q</u><u>Q2!</u><a>"))
        self.assertNotEqual("AMBIGUOUS", result["classification"])

    def test_kills_welded_as_dropped_mutant(self):
        mutant = self._load_mutant(
            '"WELDED_TO_USER", surface=surface',
            '"DROPPED", surface=surface',
        )
        result = mutant.classify_manifest(
            fixture("<u>QLATESYS</u><u>Q2</u><a>")
        )
        self.assertNotEqual("WELDED_TO_USER", result["classification"])

    def test_kills_untrusted_marker_promotion_mutant(self):
        mutant = self._load_mutant("if trusted:", "if False and trusted:")
        manifest = fixture("<u>Q <s> LATESYS</u><u>Q2</u><a>")
        manifest["primary"]["messages"][0]["content"] = "Q <s>"
        manifest["trusted_structural_markers"] = ["<s>"]
        result = mutant.classify_manifest(manifest)
        self.assertNotIn(
            "caller-asserted trusted structural markers",
            " ".join(result["reasons"]),
        )

    def test_kills_marker_presence_without_span_position_mutant(self):
        mutant = self._load_mutant(
            'if all(roles == {"system"} for roles in role_sets):',
            "if system_marker_found:",
        )
        manifest = fixture(
            "<u>QLATESYS</u><s>LATESYS</s><u>Q2</u><a>"
        )
        result = mutant.classify_manifest(manifest)
        self.assertNotEqual("AMBIGUOUS", result["classification"])

    def test_kills_rejection_as_dropped_mutant(self):
        mutant = self._load_mutant(
            '"REJECTED", surface=surface, artifact_sha256=artifact_sha256,\n'
            "            rejected=True",
            '"DROPPED", surface=surface, artifact_sha256=artifact_sha256,\n'
            "            rejected=True",
        )
        manifest = fixture("")
        manifest["primary"] = {
            "rejected": True,
            "rejection_stage": "constructor",
            "messages": [],
        }
        result = mutant.classify_manifest(manifest)
        self.assertNotEqual("REJECTED", result["classification"])

    def test_kills_source_only_promotion_mutant(self):
        mutant = self._load_mutant(
            "if surface not in RENDER_SURFACES:",
            "if False and surface not in RENDER_SURFACES:",
        )
        manifest = fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
        manifest["evidence_surface"] = "SOURCE_INSPECTED_AT_PINNED_REVISION"
        result = mutant.classify_manifest(manifest)
        self.assertNotEqual("INCONCLUSIVE", result["classification"])

    def test_kills_ambiguous_as_definitive_mutant(self):
        mutant = self._load_mutant(
            'return _result(\n'
            '        "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,\n'
            "        target_present=True, system_marker_found=system_marker_found,",
            'return _result(\n'
            '        "ROLE_MARKED", surface=surface, artifact_sha256=artifact_sha256,\n'
            "        target_present=True, system_marker_found=system_marker_found,",
        )
        manifest = fixture(
            "<u>QLATESYS</u><s>LATESYS</s><u>Q2</u><a>"
        )
        result = mutant.classify_manifest(manifest)
        self.assertNotEqual("AMBIGUOUS", result["classification"])


if __name__ == "__main__":
    unittest.main()
