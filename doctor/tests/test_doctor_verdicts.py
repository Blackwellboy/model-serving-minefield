#!/usr/bin/env python3
"""Verdict regression suite for minefield_doctor.

The doctor's contract is that anything it cannot verify goes to COULD NOT CHECK
or INCONCLUSIVE, never to CHECKED AND CLEAN. That contract is only worth
anything if it is enforced mechanically, so this suite drives the doctor
against fixture lanes whose behaviour is declared exactly, and asserts the
verdict it produces for each.

Structural invariants enforced for every scenario:

  * every CLEAN carries at least one assertion, and every one of them HELD.
    A clean verdict with no evidence behind it fails the build.
  * every INCONCLUSIVE and every COULD NOT CHECK carries at least one
    assertion that did NOT hold. That is what makes it not-clean.
  * the coverage arithmetic adds up and no trap id is counted twice.
  * REGISTRY_TRAP_COUNT still matches the number of trap files in the tree.

Each defect scenario is paired with a control lane that differs only in the
flag under test, so a passing test means the doctor discriminates, not merely
that it always says the same thing.

    python3 doctor/tests/test_doctor_verdicts.py
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_server import (FixtureLane, FixtureHub, llamacpp_props,  # noqa: E402
                            TEMPLATE_WITH_EFFORT, TEMPLATE_WITHOUT_EFFORT)

REPO_ROOT = HERE.parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


md = _load(REPO_ROOT / "doctor" / "minefield_doctor.py", "minefield_doctor")


def diagnose(base, hf_repo=None, hf_revision="main", hub=None):
    """Run every check against `base` and return the populated Doc."""
    prev_hf = md.HF_BASE
    if hub:
        md.HF_BASE = hub
    try:
        doc = md.Doc()
        b = base.rstrip("/")
        root = b[:-3].rstrip("/")
        if not md.detect_stack(doc, b, root, None):
            raise AssertionError("fixture lane did not answer /v1/models")
        args = SimpleNamespace(base_url=b, api_key=None, model=None,
                               hf_repo=hf_repo, hf_revision=hf_revision,
                               report=False, json=None)
        md.run(doc, b, root, args)
        return doc
    finally:
        md.HF_BASE = prev_hf


def codes(doc, level=None):
    return {f["code"] for f in doc.findings
            if level is None or f["level"] == level}


def find(doc, code):
    hits = [f for f in doc.findings if f["code"] == code]
    return hits[0] if hits else None


class DoctorVerdictCase(unittest.TestCase):
    """Adds the structural invariants to every assertion made below."""

    def check_structure(self, doc):
        for f in doc.findings:
            where = f"{f['level']}/{f['code']}"
            if f["level"] == "OK":
                self.assertTrue(f["assertions"],
                                f"{where}: a CLEAN verdict with no assertions")
                for a in f["assertions"]:
                    self.assertEqual(a["result"], "held",
                                     f"{where}: CLEAN emitted over a failed "
                                     f"assertion {a['assert']!r}")
            elif f["level"] in ("INCONCLUSIVE", "UNKNOWN"):
                self.assertTrue(
                    any(a["result"] == "failed" for a in f["assertions"]),
                    f"{where}: not-clean verdict with nothing unverified")
            self.assertTrue(f["title"], f"{where}: empty title")
            if f["level"] != "OK":
                self.assertTrue(f["detail"], f"{where}: no reason given")

        cov = md.coverage(doc)
        buckets = [set(cov["problems"]), set(cov["clean"]), set(cov["inconclusive"])]
        for i, a in enumerate(buckets):
            for b in buckets[i + 1:]:
                self.assertFalse(a & b, f"trap id counted in two buckets: {a & b}")
        self.assertEqual(set(cov["executed"]),
                         set(cov["problems"]) | set(cov["clean"]))
        self.assertLessEqual(len(cov["implemented"]), cov["registry_total"])
        self.assertEqual(cov["not_implemented_count"],
                         cov["registry_total"] - len(cov["implemented"]))

    def no_clean_for(self, doc, trap_id):
        for f in doc.clean:
            self.assertNotIn(trap_id, f["traps"],
                             f"trap {trap_id} reported CLEAN by "
                             f"{f['code']}: {f['title'][:90]}")


# --------------------------------------------------------------------------
# Task 1a: the server accepts an invented kwarg but no template is readable.
# --------------------------------------------------------------------------

class TestKwargTemplateUnavailable(DoctorVerdictCase):

    def test_no_template_is_not_clean(self):
        # vLLM-shaped lane: no /props, so no template can be read.
        with FixtureLane(props=None) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "07")
        f = find(doc, "KWARG_ACCEPTED_TEMPLATE_UNREADABLE")
        self.assertIsNotNone(f, "no verdict for the unreadable-template case")
        self.assertEqual(f["level"], "UNKNOWN")
        self.assertIn("07", f["traps"])
        self.assertIn("acceptance proves nothing", f["detail"])

    def test_control_template_reads_the_kwarg_is_clean(self):
        with FixtureLane(props=llamacpp_props(TEMPLATE_WITH_EFFORT)) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "KWARG_READ_BY_TEMPLATE")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "OK")

    def test_control_template_does_not_read_the_kwarg_is_a_problem(self):
        with FixtureLane(props=llamacpp_props(TEMPLATE_WITHOUT_EFFORT)) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "KWARG_ACCEPTED_BUT_DEAD")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "PROBLEM")

    def test_rejection_is_only_credited_when_attributable(self):
        # Loud lane: rejects any unknown kwarg. This one earns its CLEAN.
        with FixtureLane(kwarg_rejection="unknown") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "KWARG_UNKNOWN_REJECTED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "OK")

        # Lane that rejects reasoning_effort but silently swallows invented
        # names. The old code credited this as strict. It is the opposite.
        with FixtureLane(kwarg_rejection="known") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "07")
        f = find(doc, "KWARG_REJECTION_FROM_KNOWN_NAME")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "INCONCLUSIVE")


# --------------------------------------------------------------------------
# Task 1b: thinking-on returns no reasoning field and no think tags.
# --------------------------------------------------------------------------

class TestIgnoredThinkingKwarg(DoctorVerdictCase):

    def test_silence_is_not_clean(self):
        with FixtureLane(reasoning_field=None) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "01")
        f = find(doc, "THINKING_ON_NO_REASONING")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "UNKNOWN")
        # the six candidate states must be spelled out, not hand-waved
        for token in ("(1)", "(2)", "(3)", "(4)", "(5)", "(6)"):
            self.assertIn(token, f["detail"])

    def test_accepted_and_ignored_kwarg_yields_a_vacuous_toggle_map(self):
        with FixtureLane(thinking_effective=False) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "03")
        self.no_clean_for(doc, "01")
        f = find(doc, "TOGGLE_MAP_VACUOUS")
        self.assertIsNotNone(f, "a map where nothing fires was reported as a map")
        self.assertEqual(f["level"], "UNKNOWN")
        self.assertEqual(sorted(f["traps"]), ["03", "29"])

    def test_control_reasoning_present_is_clean(self):
        with FixtureLane(reasoning_field="reasoning") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "REASONING_FIELD_IDENTIFIED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "OK")
        self.assertIn("reasoning", f["title"])
        self.assertIsNotNone(find(doc, "TOGGLE_MAP_CHARACTERISED"))


# --------------------------------------------------------------------------
# Task 3: the tool probe must separate "did not call" from "cannot call".
# --------------------------------------------------------------------------

class TestToolProbe(DoctorVerdictCase):

    def test_non_tool_calling_model_with_forced_control_is_a_problem(self):
        with FixtureLane(tool_calls="never", tool_choice_supported=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "TOOL_CALLING_UNAVAILABLE")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "PROBLEM")
        self.assertIn("FORCED", f["title"])

    def test_without_a_forced_control_the_verdict_is_inconclusive(self):
        with FixtureLane(tool_calls="never", tool_choice_supported=False) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "19")
        # and it must NOT be asserted as a parser/template fault
        self.assertIsNone(find(doc, "TOOL_CALLING_UNAVAILABLE"))
        f = find(doc, "MODEL_DID_NOT_CALL")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "INCONCLUSIVE")
        self.assertIn("CONFIDENCE: LOW", f["detail"])
        for token in ("(1)", "(2)", "(3)", "(4)", "(5)", "(6)"):
            self.assertIn(token, f["detail"])

    def test_model_elects_not_to_call_is_distinguished(self):
        with FixtureLane(tool_calls="forced_only") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "MODEL_ELECTS_NOT_TO_CALL")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "OK")
        self.assertIsNone(find(doc, "TOOL_CALLING_UNAVAILABLE"))

    def test_unparsed_markup_is_still_caught(self):
        with FixtureLane(tool_markup=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "TOOL_MARKUP_NOT_PARSED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "PROBLEM")
        self.assertIn("26", f["traps"])

    def test_control_working_tools_is_clean(self):
        with FixtureLane(tool_calls="always") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(find(doc, "TOOL_CALLS_RETURNED")["level"], "OK")
        self.assertEqual(find(doc, "TOOL_MARKUP_PARSED")["level"], "OK")


# --------------------------------------------------------------------------
# Task 2: revision pinning.
# --------------------------------------------------------------------------

MAIN_SHA = "1111111111111111111111111111111111111111"
PIN_SHA = "2222222222222222222222222222222222222222"

HUB_REPOS = {
    "acme/demo": {"revisions": {
        # main has moved on to 0.9; the operator is serving the pinned 0.6
        "main": {"sha": MAIN_SHA, "files": {
            "generation_config.json": {"temperature": 0.9, "top_p": 0.95},
            "config.json": {"model_type": "demo"}}},
        "v1.0": {"sha": PIN_SHA, "files": {
            "generation_config.json": {"temperature": 0.6, "top_p": 0.95},
            "config.json": {"model_type": "demo"}}},
    }},
    "acme/nvfp4": {"revisions": {
        "main": {"sha": MAIN_SHA, "files": {
            "generation_config.json": {"temperature": 0.6, "top_p": 0.95},
            "config.json": {"model_type": "demo"},
            "hf_quant_config.json": {"producer": {"name": "modelopt"},
                                     "quantization": {"quant_algo": "NVFP4"}}}},
    }},
}


class TestRevisionPinning(DoctorVerdictCase):

    def test_default_main_reports_drift_against_a_moved_ref(self):
        with FixtureHub(HUB_REPOS) as hub, \
                FixtureLane(props=llamacpp_props(temperature=0.6)) as base:
            doc = diagnose(base, hf_repo="acme/demo", hub=hub)
        self.check_structure(doc)
        f = find(doc, "SAMPLING_DEFAULTS_DIFFER")
        self.assertIsNotNone(f, "drift against mutable main was not reported")
        self.assertEqual(f["level"], "PROBLEM")
        self.assertIn("@ main", f["title"])
        self.assertIn(MAIN_SHA[:12], f["title"])

    def test_pinned_revision_is_clean_and_names_the_commit(self):
        with FixtureHub(HUB_REPOS) as hub, \
                FixtureLane(props=llamacpp_props(temperature=0.6)) as base:
            doc = diagnose(base, hf_repo="acme/demo", hf_revision="v1.0", hub=hub)
        self.check_structure(doc)
        self.assertIsNone(find(doc, "SAMPLING_DEFAULTS_DIFFER"),
                          "a correctly pinned revision was still reported as drift")
        f = find(doc, "SAMPLING_DEFAULTS_MATCH")
        self.assertIsNotNone(f)
        self.assertIn("@ v1.0", f["title"])
        self.assertIn(PIN_SHA[:12], f["title"])
        self.assertEqual(doc.evidence["hf"]["resolved_commit"], PIN_SHA)
        self.assertEqual(doc.evidence["hf"]["requested_revision"], "v1.0")

    def test_unresolvable_revision_is_flagged_not_silently_used(self):
        with FixtureHub(HUB_REPOS) as hub, \
                FixtureLane(props=llamacpp_props(temperature=0.6)) as base:
            doc = diagnose(base, hf_repo="acme/demo", hf_revision="no-such-tag",
                           hub=hub)
        self.check_structure(doc)
        f = find(doc, "HF_REVISION_UNRESOLVED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "INCONCLUSIVE")

    def test_nvfp4_manifest_outside_config_json_is_found(self):
        with FixtureHub(HUB_REPOS) as hub, FixtureLane() as base:
            doc = diagnose(base, hf_repo="acme/nvfp4", hub=hub)
        self.check_structure(doc)
        f = find(doc, "QUANT_IN_HF_QUANT_CONFIG")
        self.assertIsNotNone(f, "a ModelOpt NVFP4 checkpoint was read as "
                                "unquantized")
        self.assertIn("NVFP4", f["title"])

    def test_no_hf_repo_leaves_the_config_traps_unchecked(self):
        with FixtureLane() as base:
            doc = diagnose(base)
        self.check_structure(doc)
        for t in ("10", "17", "21"):
            self.no_clean_for(doc, t)


# --------------------------------------------------------------------------
# Task 4: coverage reporting.
# --------------------------------------------------------------------------

class TestCoverage(DoctorVerdictCase):

    def test_registry_count_matches_the_tree(self):
        traps = REPO_ROOT / "traps"
        ids = {p.name[:2] for p in traps.glob("*/*.md")}
        self.assertEqual(len(ids), md.REGISTRY_TRAP_COUNT,
                         f"REGISTRY_TRAP_COUNT is {md.REGISTRY_TRAP_COUNT} but "
                         f"the tree holds {len(ids)} numbered traps: {sorted(ids)}")

    def test_every_implemented_id_exists_in_the_registry(self):
        traps = REPO_ROOT / "traps"
        for n, rel in md.TRAP_PATHS.items():
            self.assertTrue((traps / rel).exists(),
                            f"trap {n} links to {rel}, which does not exist")

    def test_coverage_line_shape_and_arithmetic(self):
        with FixtureLane() as base:
            doc = diagnose(base)
        cov = md.coverage(doc)
        line = md.coverage_line(cov)
        for token in ("implemented", "executed on this stack", "clean",
                      "problems", "inconclusive", "not implemented"):
            self.assertIn(token, line)
        self.assertIn(f"implemented {len(md.TRAP_PATHS)}/42", line)
        self.assertEqual(len(cov["clean"]) + len(cov["problems"]),
                         len(cov["executed"]))
        # a run with no --hf-repo cannot have executed the hub-only traps
        self.assertFalse(set(cov["executed"]) & md.TRAPS_NEED_HF_REPO)

    def test_coverage_block_is_printed_and_names_the_caveats(self):
        import io
        from contextlib import redirect_stdout
        with FixtureLane() as base:
            doc = diagnose(base)
        buf = io.StringIO()
        with redirect_stdout(buf):
            md.emit(doc, SimpleNamespace(base_url="http://fixture", report=False))
        out = buf.getvalue()
        self.assertIn("== COVERAGE ==", out)
        self.assertIn("implemented 17/42", out)
        self.assertIn("== INCONCLUSIVE (", out)
        self.assertIn("no check in this tool", out)
        for n in md.TRAPS_SHARED_HEURISTIC:
            self.assertIn(f"- {n}:", out)

    def test_json_output_carries_the_assertions_that_ran(self):
        with FixtureLane(reasoning_field=None) as base:
            doc = diagnose(base)
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as fh:
            path = fh.name
        cov = md.coverage(doc)
        with open(path, "w") as f:
            json.dump({"coverage": cov, "findings": doc.findings}, f, default=str)
        data = json.loads(Path(path).read_text())
        Path(path).unlink()
        self.assertTrue(data["findings"])
        for rec in data["findings"]:
            self.assertIn("assertions", rec)
            self.assertIn("code", rec)
            self.assertIn("level", rec)
        flat = [a for rec in data["findings"] for a in rec["assertions"]]
        self.assertTrue(any(a["result"] == "failed" for a in flat))
        self.assertTrue(any(a["result"] == "held" for a in flat))


# --------------------------------------------------------------------------
# History assembly and the remaining shared-heuristic traps.
# --------------------------------------------------------------------------

class TestHistoryAssembly(DoctorVerdictCase):

    def test_stripped_history_finds_the_gate(self):
        with FixtureLane(preserve_history=False) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "HISTORY_STRIPPED_GATE_FOUND")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "PROBLEM")
        self.assertIn("preserve_thinking", f["title"])

    def test_control_preserved_history_is_clean(self):
        with FixtureLane(preserve_history=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(find(doc, "WRITE_FIELD_IDENTIFIED")["level"], "OK")
        self.assertEqual(find(doc, "NO_EMPTY_THINK_SHELLS")["level"], "OK")

    def test_no_render_path_is_could_not_check(self):
        with FixtureLane(render=False) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        for t in ("04", "20", "25"):
            self.no_clean_for(doc, t)
        f = find(doc, "NO_RENDER_PATH")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "UNKNOWN")


class TestCeiling(DoctorVerdictCase):

    def test_empty_at_cap_is_a_problem(self):
        with FixtureLane(ceiling="empty_at_cap") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(find(doc, "EMPTY_CONTENT_AT_CAP")["level"], "PROBLEM")

    def test_empty_without_a_cap_hit_is_not_clean(self):
        with FixtureLane(ceiling="empty_not_at_cap") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "12")
        self.assertEqual(find(doc, "EMPTY_CONTENT_NOT_AT_CAP")["level"],
                         "INCONCLUSIVE")

    def test_control_content_present_is_clean(self):
        with FixtureLane(ceiling="content") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(find(doc, "CONTENT_PRESENT_AT_CEILING")["level"], "OK")


class TestStreamingAndMultimodal(DoctorVerdictCase):

    def test_answer_in_reasoning_deltas_is_a_problem(self):
        with FixtureLane(stream_channel="reasoning") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(find(doc, "STREAM_ANSWER_IN_REASONING")["level"],
                         "PROBLEM")

    def test_text_only_lane_must_name_the_modality_to_be_credited(self):
        with FixtureLane(accepts_images=False,
                         image_reject_names_modality=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(find(doc, "MM_REJECTED_NAMING_MODALITY")["level"], "OK")

        with FixtureLane(accepts_images=False,
                         image_reject_names_modality=False) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "MM_SURFACE_UNKNOWN")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "UNKNOWN")

    def test_audio_and_video_are_always_declared_uncovered(self):
        with FixtureLane() as base:
            doc = diagnose(base)
        f = find(doc, "MM_AUDIO_VIDEO_NOT_PROBED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
