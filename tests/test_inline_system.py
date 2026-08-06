import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from minefield.cli import main as cli_main
from minefield.inline_system import EvidenceError, classify_manifest, inspect_template

ROOT = Path(__file__).resolve().parents[1]


def fixture(
    primary: str,
    no_system: str = "<u>Q</u><u>Q2</u><a>",
    leading_system: str = "<s>S</s><u>Q</u><a>",
) -> dict:
    return {
        "schema_version": "1.0",
        "model": {"name": "fixture/model", "revision": "0" * 40},
        "evidence_surface": "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
        "target_texts": ["LATESYS"],
        "leading_system_text": "S",
        "markers": [
            {"role": "system", "open": "<s>", "close": "</s>"},
            {"role": "user", "open": "<u>", "close": "</u>"},
            {"role": "assistant", "open": "<a>"},
            {"role": "tool", "open": "<tool>", "close": "</tool>"},
        ],
        "primary": {
            "rendered_text": primary,
            "messages": [
                {"role": "user", "content": "Q"},
                {"role": "system", "content": "LATESYS"},
                {"role": "user", "content": "Q2"},
            ],
        },
        "controls": {
            "no_system": {"rendered_text": no_system},
            "leading_system": {"rendered_text": leading_system},
        },
    }


class InlineSystemClassifierTests(unittest.TestCase):
    def test_role_marked(self):
        result = classify_manifest(
            fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
        )
        self.assertEqual("ROLE_MARKED", result["classification"])
        self.assertEqual(["system"], result["roles_by_target"]["LATESYS"])

    def test_dropped_requires_exact_no_system_control(self):
        result = classify_manifest(fixture("<u>Q</u><u>Q2</u><a>"))
        self.assertEqual("DROPPED", result["classification"])
        self.assertTrue(result["matches_no_system_control"])
        self.assertIn("lossy", " ".join(result["reasons"]))

        changed = classify_manifest(fixture("<u>Q</u><u>Q2!</u><a>"))
        self.assertEqual("AMBIGUOUS", changed["classification"])

    def test_welded_to_user(self):
        result = classify_manifest(
            fixture("<u>QLATESYS</u><u>Q2</u><a>")
        )
        self.assertEqual("WELDED_TO_USER", result["classification"])
        self.assertTrue(result["inside_user_span"])

    def test_rejected_endpoint(self):
        manifest = fixture("")
        manifest["evidence_surface"] = "ENDPOINT_RENDER_REPRODUCED"
        manifest["primary"] = {
            "rejected": True,
            "rejection_stage": "request_validation",
            "endpoint_response": {"status": 400, "error": "unsupported role"},
            "messages": [],
        }
        result = classify_manifest(manifest)
        self.assertEqual("REJECTED", result["classification"])
        self.assertTrue(result["rejected"])

    def test_unmarked_target_is_ambiguous(self):
        result = classify_manifest(fixture("Q LATESYS Q2"))
        self.assertEqual("AMBIGUOUS", result["classification"])

    def test_marker_in_message_content_is_not_trusted_as_structural(self):
        manifest = fixture("<u>Q <s> LATESYS</u><u>Q2</u><a>")
        manifest["primary"]["messages"][0]["content"] = "Q <s>"
        result = classify_manifest(manifest)
        self.assertEqual("AMBIGUOUS", result["classification"])
        self.assertIn("user-supplied", " ".join(result["reasons"]))

    def test_multiple_inline_system_messages(self):
        manifest = fixture("<u>Q</u><s>SYS1</s><s>SYS2</s><u>Q2</u><a>")
        manifest["target_texts"] = ["SYS1", "SYS2"]
        manifest["primary"]["messages"] = [
            {"role": "user", "content": "Q"},
            {"role": "system", "content": "SYS1"},
            {"role": "system", "content": "SYS2"},
            {"role": "user", "content": "Q2"},
        ]
        result = classify_manifest(manifest)
        self.assertEqual("ROLE_MARKED", result["classification"])

    def test_system_after_tool_result(self):
        manifest = fixture(
            "<u>Q</u><tool>RESULT</tool><s>LATESYS</s><u>Q2</u><a>"
        )
        manifest["primary"]["messages"].insert(
            1, {"role": "tool", "content": "RESULT"}
        )
        result = classify_manifest(manifest)
        self.assertEqual("ROLE_MARKED", result["classification"])

    def test_custom_delimiters(self):
        manifest = fixture("[U]Q[/U][S]LATESYS[/S][U]Q2[/U][A]")
        manifest["markers"] = [
            {"role": "system", "open": "[S]", "close": "[/S]"},
            {"role": "user", "open": "[U]", "close": "[/U]"},
            {"role": "assistant", "open": "[A]"},
        ]
        manifest["controls"]["leading_system"]["rendered_text"] = (
            "[S]S[/S][U]Q[/U][A]"
        )
        result = classify_manifest(manifest)
        self.assertEqual("ROLE_MARKED", result["classification"])

    def test_token_and_decoded_disagreement_is_inconclusive(self):
        manifest = fixture("<u>QLATESYS</u><u>Q2</u><a>")
        manifest["primary"]["decoded_from_token_ids"] = (
            "<u>Q</u><s>LATESYS</s><u>Q2</u><a>"
        )
        result = classify_manifest(manifest)
        self.assertEqual("INCONCLUSIVE", result["classification"])

    def test_raw_token_strings_are_supplemental_only(self):
        manifest = fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
        manifest["primary"]["token_strings"] = [
            "▁<u>", "Q", "</u>", "Ġ<s>", "LATESYS", "</s>",
            "▁<u>", "Q2", "</u>", "<a>",
        ]
        result = classify_manifest(manifest)
        self.assertEqual("ROLE_MARKED", result["classification"])

    def test_decoded_token_strings_can_be_authoritative(self):
        manifest = fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
        manifest["primary"].pop("rendered_text")
        manifest["primary"]["token_strings"] = [
            "▁<u>", "Q", "</u>", "Ġ<s>", "LATESYS", "</s>",
            "▁<u>", "Q2", "</u>", "<a>",
        ]
        manifest["primary"]["decoded_from_token_strings"] = (
            "<u>Q</u><s>LATESYS</s><u>Q2</u><a>"
        )
        result = classify_manifest(manifest)
        self.assertEqual("ROLE_MARKED", result["classification"])

    def test_source_and_output_surfaces_never_promote(self):
        for surface in (
            "SOURCE_INSPECTED_AT_PINNED_REVISION",
            "MODEL_OUTPUT_REPRODUCED",
            "UNDER_TEST",
            "INCONCLUSIVE",
        ):
            with self.subTest(surface=surface):
                manifest = fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
                manifest["evidence_surface"] = surface
                manifest["primary"]["rejected"] = True
                result = classify_manifest(manifest)
                self.assertEqual("INCONCLUSIVE", result["classification"])

    def test_output_is_deterministic(self):
        manifest = fixture("<u>QLATESYS</u><u>Q2</u><a>")
        self.assertEqual(classify_manifest(manifest), classify_manifest(manifest))

    def test_malformed_and_oversized_manifests_are_rejected(self):
        with self.assertRaises(EvidenceError):
            classify_manifest({
                "evidence_surface": "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
                "primary": {"rendered_text": "x"},
                "controls": [],
            })
        with self.assertRaises(EvidenceError):
            classify_manifest({
                "evidence_surface": "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
                "primary": {"rendered_text": "x" * (4 * 1024 * 1024 + 1)},
            })

    def test_template_is_hashed_but_not_executed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "template.jinja"
            path.write_text("{{ raise_if_executed() }}", encoding="utf-8")
            result = inspect_template(path)
            self.assertEqual("SOURCE_INSPECTED_AT_PINNED_REVISION",
                             result["evidence_surface"])
            self.assertEqual(25, result["bytes"])

    def test_cli_emits_json(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest_path = Path(folder) / "manifest.json"
            manifest_path.write_text(
                json.dumps(fixture("<u>QLATESYS</u><u>Q2</u><a>")),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, cli_main([
                    "classify-inline-system", "--manifest", str(manifest_path)
                ]))
            self.assertEqual(
                "WELDED_TO_USER", json.loads(output.getvalue())["classification"]
            )

    def test_cli_malformed_evidence_uses_exit_two_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest_path = Path(folder) / "manifest.json"
            manifest_path.write_text("[]", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(2, cli_main([
                    "classify-inline-system", "--manifest", str(manifest_path)
                ]))
            parsed = json.loads(stderr.getvalue())
            self.assertEqual("INCONCLUSIVE", parsed["classification"])
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_documented_schema_and_example_are_valid_json(self):
        schema = json.loads(
            (ROOT / "docs" / "inline-system-evidence.schema.json").read_text(
                encoding="utf-8"
            )
        )
        example = json.loads(
            (ROOT / "docs" / "inline-system-evidence.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("https://json-schema.org/draft/2020-12/schema",
                         schema["$schema"])
        self.assertEqual(
            example["classification"],
            classify_manifest(example)["classification"],
        )

    def test_malformed_marker_spans_are_never_definitive(self):
        manifest = fixture("<u>Q</u><s>LATESYS<u>Q2</u><a>")
        self.assertEqual("AMBIGUOUS", classify_manifest(manifest)["classification"])

        manifest = fixture("<u>Q</u><s>LATESYS<s><u>Q2</u><a>")
        manifest["markers"][0]["close"] = "<s>"
        with self.assertRaises(EvidenceError):
            classify_manifest(manifest)

    def test_trusted_marker_override_is_not_accepted(self):
        manifest = fixture("<u>Q <s> LATESYS</u><u>Q2</u><a>")
        manifest["primary"]["messages"][0]["content"] = "Q <s>"
        manifest["trusted_structural_markers"] = ["<s>"]
        self.assertEqual("AMBIGUOUS", classify_manifest(manifest)["classification"])

    def test_definitive_labels_require_successful_controls(self):
        manifest = fixture("<u>QLATESYS</u><u>Q2</u><a>")
        manifest["controls"] = {}
        self.assertEqual("INCONCLUSIVE", classify_manifest(manifest)["classification"])

        manifest = fixture("<u>Q</u><u>Q2</u><a>")
        manifest["controls"]["no_system"]["status"] = 500
        self.assertEqual("INCONCLUSIVE", classify_manifest(manifest)["classification"])

    def test_capture_error_is_not_semantic_rejection(self):
        manifest = fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
        manifest["primary"]["error"] = "nonfatal cache warning"
        self.assertEqual("INCONCLUSIVE", classify_manifest(manifest)["classification"])

    def test_target_must_equal_system_message_payload(self):
        manifest = fixture("<u>Q LATESYSTEM</u><u>Q2</u><a>")
        manifest["target_texts"] = ["SYS"]
        self.assertEqual("AMBIGUOUS", classify_manifest(manifest)["classification"])

    def test_direct_template_execution_is_a_render_surface(self):
        manifest = fixture("<u>Q</u><s>LATESYS</s><u>Q2</u><a>")
        manifest["evidence_surface"] = "TEMPLATE_EXECUTED_AT_PINNED_REVISION"
        self.assertEqual("ROLE_MARKED", classify_manifest(manifest)["classification"])


if __name__ == "__main__":
    unittest.main()
