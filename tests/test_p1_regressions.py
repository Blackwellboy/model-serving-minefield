import contextlib
import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from minefield.cli import main as cli_main
from minefield.matching import diagnose
from minefield.mcp_server import call_tool
from minefield.redaction import redact_document, redact_text
from minefield.support_bundle import plan, write_bundle
from tests.test_diagnosis_contract import BASE_REGISTRY


class DirectProbeP1Tests(unittest.TestCase):
    def test_explicit_candidate_bypasses_lexical_filter_without_auto_confirmation(self):
        result = diagnose(
            BASE_REGISTRY, "zzzxxyyqqq", direct_probe_trap_ids=["12"]
        )
        self.assertEqual(["12"], [item["trap_id"] for item in result["matches"]])
        match = result["matches"][0]
        self.assertEqual("candidate_requested", match["direct_probe_result"])
        self.assertFalse(match["direct_probe_support"])
        self.assertNotEqual("CONFIRMED_BY_DIRECT_PROBE", match["diagnosis_level"])
        self.assertEqual("reproduced here", match["evidence_status"])

    def test_explicit_result_can_confirm_refute_or_remain_inconclusive(self):
        for outcome, level, support in (
            ("confirmed", "CONFIRMED_BY_DIRECT_PROBE", True),
            ("refuted", "NOT_APPLICABLE", False),
            ("inconclusive", "INCONCLUSIVE", False),
        ):
            with self.subTest(outcome=outcome):
                match = diagnose(
                    BASE_REGISTRY,
                    "no lexical overlap",
                    direct_probe_results={"12": outcome},
                )["matches"][0]
                self.assertEqual(outcome, match["direct_probe_result"])
                self.assertEqual(level, match["diagnosis_level"])
                self.assertEqual(support, match["direct_probe_support"])
                self.assertEqual("reproduced here", match["evidence_status"])

    def test_multiple_explicit_candidates_bypass_ordinary_limit_deterministically(self):
        kwargs = {
            "direct_probe_trap_ids": ["77", "12", "45"],
            "limit": 1,
        }
        first = diagnose(BASE_REGISTRY, "empty content at token ceiling", **kwargs)
        second = diagnose(BASE_REGISTRY, "empty content at token ceiling", **kwargs)
        ids = [item["trap_id"] for item in first["matches"]]
        self.assertEqual(["12", "45", "77"], ids)
        self.assertEqual(first, second)

    def test_direct_candidate_outside_ordinary_top_result_and_mixed_matching(self):
        ordinary = diagnose(
            BASE_REGISTRY, "empty content at token ceiling", limit=1
        )
        self.assertEqual(["12"], [item["trap_id"] for item in ordinary["matches"]])
        mixed = diagnose(
            BASE_REGISTRY,
            "empty content at token ceiling",
            direct_probe_trap_ids=["77"],
            limit=1,
        )
        self.assertEqual(["77", "12"], [item["trap_id"] for item in mixed["matches"]])
        self.assertEqual("candidate_requested", mixed["matches"][0]["direct_probe_result"])

    def test_unknown_and_invalid_results_are_ignored_safely(self):
        miss = diagnose(
            BASE_REGISTRY,
            "zzzxxyyqqq",
            direct_probe_trap_ids=["999", "not-an-id"],
            direct_probe_results={"998": "confirmed", "12": "invented"},
        )
        self.assertEqual("NOT_DOCUMENTED", miss["diagnosis_level"])
        self.assertEqual([], miss["matches"])
        with self.assertRaisesRegex(ValueError, "invalid result"):
            call_tool(
                "search_symptom",
                {"direct_probe_results": {"12": "invented"}},
                BASE_REGISTRY,
            )

    def test_no_direct_probe_preserves_ordinary_behavior(self):
        without = diagnose(BASE_REGISTRY, "sustained decode stalls after model load")
        empty = diagnose(
            BASE_REGISTRY,
            "sustained decode stalls after model load",
            direct_probe_trap_ids=[],
            direct_probe_results={},
        )
        self.assertEqual(without, empty)

    def test_cli_and_mcp_expose_explicit_probe_results(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, cli_main([
                "guide", "zzzxxyyqqq",
                "--direct-probe-trap", "12",
                "--direct-probe-result", "12=refuted",
            ]))
        self.assertEqual(
            "refuted", json.loads(output.getvalue())["matches"][0]["direct_probe_result"]
        )
        mcp = call_tool(
            "search_symptom",
            {"symptom": "zzzxxyyqqq", "direct_probe_results": {"12": "confirmed"}},
            BASE_REGISTRY,
        )
        self.assertTrue(mcp["matches"][0]["direct_probe_support"])


class RedactionP1Tests(unittest.TestCase):
    SECRET = "abcdefghijklmnop"
    SECOND = "secondsecretvalue"

    def _assert_secret_removed(self, text):
        clean, report = redact_document(text)
        self.assertNotIn(self.SECRET, clean)
        self.assertTrue(report)
        return clean, report

    def test_quoted_unquoted_whitespace_nested_and_malformed_forms(self):
        cases = (
            f"api_key: {self.SECRET}",
            f'{{"api_key": "{self.SECRET}"}}',
            f"'api_key': '{self.SECRET}'",
            f'  "api_key"   :   "{self.SECRET}"  ',
            json.dumps({"outer": {"api_key": self.SECRET}}),
            json.dumps([{"safe": 1}, {"token": self.SECRET}]),
            json.dumps({"ＡＰＩ＿ＫＥＹ": self.SECRET}),
            f'log prefix {{"api_key": "{self.SECRET}", broken=true',
            f'password="{self.SECRET}"',
            f'"secret": "{self.SECRET}"!',
            f"token: {self.SECRET}\n",
        )
        for sample in cases:
            with self.subTest(sample=sample):
                self._assert_secret_removed(sample)

    def test_multiple_secrets_and_existing_bearer_formats(self):
        text = (
            f'"api_key": "{self.SECRET}", token: {self.SECOND}\n'
            "Authorization: Bearer ABCDEFGHIJKLMNOP\n"
            "Cookie: session=abcdef\n"
        )
        clean, report = redact_text(text)
        for secret in (self.SECRET, self.SECOND, "ABCDEFGHIJKLMNOP", "session=abcdef"):
            self.assertNotIn(secret, clean)
        self.assertGreaterEqual(sum(item["count"] for item in report), 4)

    def test_non_secret_prose_and_near_miss_keys_are_unchanged(self):
        safe = (
            "Documentation discusses API key rotation without assigning one. "
            "token_count: 42; secretive: false; monkey=banana; config.json"
        )
        self.assertEqual((safe, []), redact_text(safe))

    def test_preview_zip_and_issue_report_share_effective_redaction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "config.json"
            source.write_text(
                json.dumps({
                    "api_key": self.SECRET,
                    "nested": [{"password": self.SECOND}],
                    "safe": "kept",
                }),
                encoding="utf-8",
            )
            bundle_plan = plan(configs=[str(source)])
            self.assertEqual(2, sum(
                item["count"] for item in bundle_plan["preview"]["redactions"]
                if item["file"].startswith("config/")
            ))
            config_name = next(
                name for name in bundle_plan["files"] if name.startswith("config/")
            )
            preview_bytes = bundle_plan["files"][config_name]
            target = root / "bundle.zip"
            write_bundle(str(target), bundle_plan)
            with zipfile.ZipFile(target) as archive:
                written_bytes = archive.read(config_name)
                archive_text = b"".join(
                    archive.read(name) for name in archive.namelist()
                ).decode("utf-8", errors="ignore")
            self.assertEqual(preview_bytes, written_bytes)
            self.assertNotIn(self.SECRET, archive_text)
            self.assertNotIn(self.SECOND, archive_text)
            self.assertIn("kept", written_bytes.decode())

            issue = call_tool(
                "prepare_issue_report",
                {"evidence": source.read_text(encoding="utf-8")},
                BASE_REGISTRY,
            )
            self.assertNotIn(self.SECRET, issue["markdown"])
            self.assertNotIn(self.SECOND, issue["markdown"])
            self.assertIn("kept", issue["markdown"])
            self.assertEqual(2, sum(item["count"] for item in issue["redactions"]))


class P1MutationTests(unittest.TestCase):
    def test_direct_probe_mutants_are_killed(self):
        expected = diagnose(
            BASE_REGISTRY,
            "zzzxxyyqqq",
            direct_probe_trap_ids=["12", "77"],
            direct_probe_results={"12": "refuted"},
            limit=1,
        )

        def assert_contract(value):
            ids = [item["trap_id"] for item in value["matches"]]
            self.assertEqual(["12", "77"], ids)
            self.assertEqual("refuted", value["matches"][0]["direct_probe_result"])
            self.assertFalse(value["matches"][0]["direct_probe_support"])
            self.assertEqual("NOT_APPLICABLE", value["matches"][0]["diagnosis_level"])
            self.assertNotIn("999", ids)

        assert_contract(expected)
        mutants = []
        mutants.append({"diagnosis_level": "NOT_DOCUMENTED", "matches": []})
        mutants.append({**expected, "matches": expected["matches"][:1]})
        promoted = copy.deepcopy(expected)
        promoted["matches"][0]["direct_probe_support"] = True
        promoted["matches"][0]["diagnosis_level"] = "CONFIRMED_BY_DIRECT_PROBE"
        mutants.append(promoted)
        unknown = copy.deepcopy(expected)
        unknown["matches"].append({**unknown["matches"][-1], "trap_id": "999"})
        mutants.append(unknown)
        for mutant in mutants:
            with self.assertRaises(AssertionError):
                assert_contract(mutant)

    def test_redaction_mutants_are_killed(self):
        raw = json.dumps({
            "api_key": RedactionP1Tests.SECRET,
            "nested": [{"password": RedactionP1Tests.SECOND}],
        })
        clean, _ = redact_document(raw)

        def assert_clean(value):
            self.assertNotIn(RedactionP1Tests.SECRET, value)
            self.assertNotIn(RedactionP1Tests.SECOND, value)
            self.assertGreaterEqual(value.count("<REDACTED:"), 2)

        assert_clean(clean)
        mutants = (
            raw,
            clean.replace("<REDACTED:secret-field>", RedactionP1Tests.SECRET, 1),
            clean.replace("<REDACTED:secret-field>", RedactionP1Tests.SECOND, 1),
            "# Minefield report\n\n" + raw,
        )
        for mutant in mutants:
            with self.assertRaises(AssertionError):
                assert_clean(mutant)

        preview = plan()["preview"]["files"]
        changed_output = preview + [{"path": "unpreviewed.txt", "bytes": 1}]
        with self.assertRaises(AssertionError):
            self.assertEqual(preview, changed_output)


if __name__ == "__main__":
    unittest.main()
