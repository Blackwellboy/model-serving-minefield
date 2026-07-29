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
import re
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

    def test_a_template_mentioning_the_kwarg_is_not_clean(self):
        # The name appearing in the template text says the knob is REFERENCED,
        # not that it is read. TEMPLATE_WITH_EFFORT is the proof: it sets
        # reasoning_effort and then never uses it, so a grep hit and a dead
        # knob are the same observation here.
        with FixtureLane(props=llamacpp_props(TEMPLATE_WITH_EFFORT)) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "07")
        self.assertIsNone(find(doc, "KWARG_READ_BY_TEMPLATE"),
                          "a substring hit was still being called a read")
        f = find(doc, "KWARG_REFERENCED_BY_TEMPLATE")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "INCONCLUSIVE")
        self.assertIn("A reference is not a read", f["detail"])
        self.assertTrue(any(a["result"] == "failed"
                            and "changes the rendered prompt" in a["assert"]
                            for a in f["assertions"]),
                        "nothing records that the two renders were never diffed")

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
        f3 = find(doc, "TOGGLE_MAP_CHARACTERISED")
        self.assertIsNotNone(f3)
        self.assertEqual(f3["level"], "OK")

    def test_explicit_off_that_still_fires_is_a_problem(self):
        # The defect trap 03 is about. The doctor computed f_off, printed it,
        # and filed the whole map under CHECKED AND CLEAN regardless of it.
        # The lane must be one whose stack we identify, otherwise a firing off
        # arm is equally consistent with our having sent a name it never reads
        # -- see test_unidentified_stack_* below.
        with FixtureLane(explicit_off_honored=False,
                         props=llamacpp_props()) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "03")
        self.assertIsNone(find(doc, "TOGGLE_MAP_CHARACTERISED"),
                          "a lane whose off switch does nothing was reported "
                          "as a characterised toggle map")
        f = find(doc, "EXPLICIT_OFF_STILL_FIRES")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "PROBLEM")
        self.assertEqual(f["traps"], ["03"])
        self.assertIn("explicit-off still produces reasoning", f["title"])

    # -- the Ollama false-positive pair ---------------------------------
    #
    # Measured on Ollama 0.32.5 / qwen3:8b: chat_template_kwargs is accepted
    # and ignored (569 chars of reasoning with enable_thinking=false, byte
    # identical to sending nothing), while reasoning_effort=none genuinely
    # turns thinking off. The doctor reported that lane as a trap-03 PROBLEM
    # and, from the same three arms, emitted a trap-29 CLEAN asserting no
    # client kwarg could override the server default. Both were wrong, and a
    # false CLEAN on 29 is the exact defect class the hardening pass existed
    # to remove.

    def test_ollama_lane_is_not_reported_as_a_broken_off_switch(self):
        with FixtureLane(ollama=True, off_kwarg="reasoning_effort") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertEqual(doc.stack, "ollama",
                         "an Ollama lane must be identified as one; without "
                         "that the off-control spelling cannot be chosen")
        self.assertIsNone(find(doc, "EXPLICIT_OFF_STILL_FIRES"),
                          "a lane with a working off switch under a different "
                          "kwarg was reported as having no off switch")
        f = find(doc, "TOGGLE_MAP_CHARACTERISED")
        self.assertIsNotNone(f, "the toggle map is characterisable on Ollama "
                                "once the right control is sent")
        self.assertEqual(f["level"], "OK")

    def test_ollama_off_control_found_via_alternate_spelling(self):
        # Same lane, but detection deliberately defeated: no /api/version. The
        # doctor must still find the working control by trying it, rather than
        # concluding the off switch is broken.
        with FixtureLane(ollama=False, off_kwarg="reasoning_effort") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertIsNone(find(doc, "EXPLICIT_OFF_STILL_FIRES"))
        f = find(doc, "OFF_CONTROL_IS_A_DIFFERENT_KWARG")
        self.assertIsNotNone(f, "an alternate off control that demonstrably "
                                "suppresses was not searched for")
        self.assertEqual(f["level"], "OK")
        self.assertIn("reasoning_effort=none", f["title"])
        claims = {a["assert"] for a in f["assertions"]}
        self.assertTrue(any("suppresses reasoning" in c for c in claims))

    def test_unidentified_stack_with_no_working_off_control_cannot_check(self):
        # Nothing suppresses AND the stack is anonymous. "The off switch is
        # broken" and "we sent a word this stack never reads" produce this
        # identical observation, so neither may be asserted.
        with FixtureLane(explicit_off_honored=False, anonymous=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertNotIn(doc.stack, ("vllm", "llama.cpp", "ollama"),
                         "this scenario is only meaningful on a lane that "
                         "identifies as no known stack")
        self.assertIsNone(find(doc, "EXPLICIT_OFF_STILL_FIRES"),
                          "a PROBLEM was asserted about an off switch on a "
                          "stack whose off-control name was never established")
        f = find(doc, "OFF_CONTROL_NAME_NOT_ESTABLISHED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "UNKNOWN")
        self.assertEqual(f["traps"], ["03"])

    def test_unidentified_stack_gets_no_clean_on_trap_29(self):
        # The false CLEAN. NO_SERVER_SIDE_OFF_STATE asserts that no client
        # kwarg can override the server default; on an anonymous stack we have
        # tried only names we guessed, so that is a clean earned from silence.
        with FixtureLane(explicit_off_honored=False, anonymous=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "29")
        self.assertIsNone(find(doc, "NO_SERVER_SIDE_OFF_STATE"),
                          "trap 29 was cleared on a lane whose client off "
                          "control was never established")
        # and it must reach trap 29's own gate rather than being covered by
        # the trap-03 branch returning early: a mutation run showed that an
        # early return made this gate unreachable and this test vacuous.
        f = find(doc, "SERVER_GATE_CONTROL_UNKNOWN")
        self.assertIsNotNone(f, "trap 29 produced no verdict of its own, so "
                                "the gate protecting it never executed")
        self.assertEqual(f["level"], "UNKNOWN")
        self.assertEqual(f["traps"], ["29"])

    def test_trap_29_clean_is_still_available_when_the_control_is_known(self):
        # The control for the pair above: same firing-absent-arm shape, but on
        # a stack we identify, so the claim about client kwargs is earned.
        with FixtureLane(ollama=True, off_kwarg="reasoning_effort") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "NO_SERVER_SIDE_OFF_STATE")
        self.assertIsNotNone(f, "trap 29 must still be clearable when the off "
                                "control is known -- the fix must not simply "
                                "delete the verdict")
        self.assertEqual(f["level"], "OK")
        claims = {a["assert"] for a in f["assertions"]}
        self.assertTrue(any("client off control this lane reads is known" in c
                            for c in claims))

    def test_toggle_map_clean_requires_on_to_fire_and_off_not_to(self):
        # The control differs from the case above in exactly one flag.
        with FixtureLane(explicit_off_honored=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "TOGGLE_MAP_CHARACTERISED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "OK")
        claims = {a["assert"] for a in f["assertions"]}
        self.assertTrue(any("explicit-on arm fires" in c for c in claims))
        self.assertTrue(any("explicit-off arm does not fire" in c for c in claims))
        # and it must not tell the reader that leaving the kwarg out is safe
        self.assertIn("not that", f["title"])


# --------------------------------------------------------------------------
# Task 3: the tool probe must separate "did not call" from "cannot call".
# --------------------------------------------------------------------------

class TestRequestValidation(DoctorVerdictCase):
    """Trap 77. The check is three lines of logic and one of them is the
    control, so these cases mostly exist to prove the control is load-bearing.
    """

    def test_an_unvalidated_lane_is_a_problem(self):
        with FixtureLane() as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertIn("UNKNOWN_FIELD_ACCEPTED", codes(doc, "PROBLEM"))
        self.no_clean_for(doc, "77")

    def test_a_validating_lane_is_clean(self):
        with FixtureLane(validates_top_level=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.assertIn("VALIDATION_REJECTS_UNKNOWN_FIELD", codes(doc, "OK"))

    def test_the_problem_names_the_arm_consequence_not_just_the_status(self):
        """The operator cost of trap 77 is a whole experimental arm measured
        on the wrong configuration. A finding that says only "returns 200 for
        anything" reads as pedantry and gets skipped."""
        with FixtureLane() as base:
            doc = diagnose(base)
        f = [x for x in doc.findings
             if x["code"] == "UNKNOWN_FIELD_ACCEPTED"][0]
        blob = (f["title"] + " " + (f["detail"] or "")).lower()
        self.assertIn("arm", blob)
        self.assertIn("status code", blob)

    def test_a_lane_that_rejects_everything_is_not_credited(self):
        """The control. A 400 on the probe means nothing if the baseline was
        also refused: a wrong model name, an expired key or a server still
        loading produces exactly that, and crediting it would be the
        false-CLEAN shape this tool has emitted four times."""
        with FixtureLane(reject_everything=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "77")
        self.assertIn("VALIDATION_NO_BASELINE", codes(doc))


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
        f = find(doc, "TOOL_MARKUP_PARSED")
        self.assertEqual(f["level"], "OK")
        # the assertion must record what was actually seen, not a fixed word
        self.assertEqual(f["assertions"][0]["observed"], {"markup_seen": False})

    def test_markup_alongside_parsed_calls_is_not_clean(self):
        # Calls parse AND raw markup leaks. The old code emitted a CLEAN whose
        # assertion read "no raw <tool_call> markup" with markup_seen=True
        # recorded beside it as held: the log contradicted the claim.
        with FixtureLane(tool_calls="always", tool_markup_alongside=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "26")
        self.assertIsNone(find(doc, "TOOL_MARKUP_PARSED"))
        f = find(doc, "TOOL_MARKUP_PARTIALLY_PARSED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "PROBLEM")
        self.assertEqual(f["traps"], ["26"])


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
    # the other manifest location: declared inline in config.json
    "acme/inconfig": {"revisions": {
        "main": {"sha": MAIN_SHA, "files": {
            "generation_config.json": {"temperature": 0.6, "top_p": 0.95},
            "config.json": {"model_type": "demo",
                            "quantization_config": {
                                "quant_method": "compressed-tensors",
                                "ignore": ["lm_head"]}}}},
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
        self.assertIn("NVFP4", f["detail"])

    def test_a_located_quant_manifest_is_never_clean_for_trap_10(self):
        # Trap 10's failure mode is kernel path != label. A manifest on the hub
        # establishes the label and cannot reach the running engine, so neither
        # manifest location can rule the failure mode out.
        cases = [("acme/nvfp4", "QUANT_IN_HF_QUANT_CONFIG"),
                 ("acme/inconfig", "QUANT_IN_CONFIG_JSON")]
        for repo, code in cases:
            with self.subTest(repo=repo):
                with FixtureHub(HUB_REPOS) as hub, FixtureLane() as base:
                    doc = diagnose(base, hf_repo=repo, hub=hub)
                self.check_structure(doc)
                self.no_clean_for(doc, "10")
                f = find(doc, code)
                self.assertIsNotNone(f)
                self.assertEqual(f["level"], "INCONCLUSIVE")
                self.assertIn("different kernel path", f["detail"])
                # it must name a runtime tell the reader can actually run
                self.assertIn("backend-selection log", f["detail"])
                self.assertTrue(
                    any(a["result"] == "failed" and "runtime tell" in a["assert"]
                        for a in f["assertions"]),
                    "nothing records that no runtime tell was read")

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
        ids = {mm.group(1) for mm in
               (re.match(r"^(\d{2,})-", p.name)
                for p in traps.glob("*/*.md")) if mm}
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
        self.assertIn(f"implemented {len(md.TRAP_PATHS)}/{md.REGISTRY_TRAP_COUNT}", line)
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
        self.assertIn(f"implemented {len(md.TRAP_PATHS)}/{md.REGISTRY_TRAP_COUNT}", out)
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

    def test_absent_think_shells_do_not_clear_trap_04(self):
        # A lane that drops prior reasoning and emits no wrapper at all
        # produces a render with no empty think shells. That absence rules out
        # trap 25, which is about the wrappers. It cannot rule out trap 04,
        # which is about the reasoning being gone. Trap 04 gets its verdict
        # from the write-field probe, on evidence that can settle it.
        with FixtureLane(preserve_history=True) as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "NO_EMPTY_THINK_SHELLS")
        self.assertEqual(f["traps"], ["25"],
                         f"the empty-shell render still clears {f['traps']}")
        # 04 is still legitimately clean here, but from the other finding
        self.assertIn("04", find(doc, "WRITE_FIELD_IDENTIFIED")["traps"])

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

    def test_empty_at_cap_does_not_tag_traps_22_and_16(self):
        # The finding is a single probe at a single budget. Trap 22 needs a
        # cross-size comparison and trap 16 is about scoring finish_reason,
        # so tagging either onto this one observation over-claims both.
        with FixtureLane(ceiling="empty_at_cap") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "EMPTY_CONTENT_AT_CAP")
        self.assertEqual(f["traps"], ["12"],
                         f"one ceiling probe still tags {f['traps']}")

    def test_trap_22_is_never_given_a_verdict_by_one_probe(self):
        # In every ceiling scenario, 22 must land in COULD NOT CHECK and never
        # in CLEAN or PROBLEM: a floor is a distribution and this tool sends
        # one request at one budget.
        for mode in ("content", "content_at_cap", "empty_at_cap",
                     "empty_not_at_cap"):
            with self.subTest(ceiling=mode):
                with FixtureLane(ceiling=mode) as base:
                    doc = diagnose(base)
                self.check_structure(doc)
                self.no_clean_for(doc, "22")
                for f in doc.problems:
                    self.assertNotIn("22", f["traps"],
                                     f"{f['code']} claims a trap-22 verdict")
                f = find(doc, "BUDGET_FLOOR_NOT_CHARACTERISED")
                self.assertIsNotNone(f)
                self.assertEqual(f["level"], "UNKNOWN")

    def test_empty_without_a_cap_hit_is_not_clean(self):
        with FixtureLane(ceiling="empty_not_at_cap") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "12")
        self.assertEqual(find(doc, "EMPTY_CONTENT_NOT_AT_CAP")["level"],
                         "INCONCLUSIVE")

    def test_content_present_without_reaching_the_cap_is_not_clean(self):
        # One request at max_tokens=512 that finished early never exercised
        # the empty-at-cap failure mode. The old code called this CLEAN for
        # trap 12, and the old test locked that in.
        with FixtureLane(ceiling="content") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        self.no_clean_for(doc, "12")
        self.assertIsNone(find(doc, "CONTENT_PRESENT_AT_CEILING"),
                          "an early finish is still being read as a negative "
                          "for empty-at-cap")
        f = find(doc, "CEILING_NOT_REACHED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "INCONCLUSIVE")
        self.assertIn("never reached the cap", f["detail"])

    def test_control_content_at_a_real_cap_hit_is_clean(self):
        # Differs from the case above in exactly one thing: the cap was
        # actually reached. That is what rules the failure mode out.
        with FixtureLane(ceiling="content_at_cap") as base:
            doc = diagnose(base)
        self.check_structure(doc)
        f = find(doc, "CONTENT_PRESENT_AT_CAP_HIT")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "OK")
        self.assertEqual(f["traps"], ["12"])
        claims = {a["assert"] for a in f["assertions"]}
        self.assertTrue(any("reached the token cap" in c for c in claims))


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

    def test_advisory_checks_are_labelled_as_outside_the_registry(self):
        # mm-* checks can emit PROBLEM and CLEAN of their own, and there is no
        # trap file or README row behind any of them. The output must say so
        # rather than printing them as "registry draft", which reads like an
        # entry that is on its way in.
        import io
        from contextlib import redirect_stdout
        with FixtureLane() as base:
            doc = diagnose(base)
        buf = io.StringIO()
        with redirect_stdout(buf):
            md.emit(doc, SimpleNamespace(base_url="http://fixture", report=False))
        out = buf.getvalue()
        for n in md.ADVISORY_IDS:
            self.assertNotIn(f"registry draft: {n}", out,
                             f"{n} is still presented as a pending entry")
        self.assertIn("advisory, not in the registry", out)
        self.assertIn("advisory checks, counted nowhere above", out)
        # and none of them may leak into the trap-id coverage arithmetic
        cov = md.coverage(doc)
        for bucket in ("clean", "problems", "inconclusive", "executed"):
            self.assertFalse(set(cov[bucket]) & set(md.ADVISORY_IDS),
                             f"an advisory id was counted in {bucket}")

    def test_never_clean_checks_are_declared_in_coverage(self):
        import io
        from contextlib import redirect_stdout
        with FixtureLane() as base:
            doc = diagnose(base)
        buf = io.StringIO()
        with redirect_stdout(buf):
            md.emit(doc, SimpleNamespace(base_url="http://fixture", report=False))
        out = buf.getvalue()
        self.assertIn("NEVER REACHES CLEAN", out)
        for n in md.TRAPS_NEVER_CLEAN:
            self.assertIn(f"- {n}: NEVER REACHES CLEAN", out)

    def test_audio_and_video_are_always_declared_uncovered(self):
        with FixtureLane() as base:
            doc = diagnose(base)
        f = find(doc, "MM_AUDIO_VIDEO_NOT_PROBED")
        self.assertIsNotNone(f)
        self.assertEqual(f["level"], "UNKNOWN")


# --------------------------------------------------------------------------
# The contract itself. Three separate hardening passes each converted the
# false CLEANs they happened to look at and each missed others, so the guard
# is no longer "review the ok() calls". Every CLEAN this tool can emit is
# enumerated here with the failure mode it rules OUT. A new one cannot appear
# without landing in this table, and a reviewer reading the table can check
# the rule rather than rediscovering it.
# --------------------------------------------------------------------------

CLEAN_CONTRACT = {
    "REASONING_FIELD_IDENTIFIED":
        "a reasoning field came back non-empty, so which name to read is "
        "settled by observation, not inferred from silence",
    "NO_ORPHANED_CLOSE_THINK":
        "all three arms returned and none began with </think>; the failure "
        "signature is the leading tag itself, and it was absent in every arm "
        "that was inspected (the partial case is INCONCLUSIVE)",
    "TOGGLE_MAP_CHARACTERISED":
        "explicit-on fired and explicit-off did not, so the two arms are "
        "separable AND the off arm is genuinely off",
    "NO_SERVER_SIDE_OFF_STATE":
        "the kwarg-absent arm fires, so there is no server-side off state for "
        "a client kwarg to override -- and the client control this lane reads "
        "is known, so the claim about client kwargs is not made from silence",
    "OFF_CONTROL_IS_A_DIFFERENT_KWARG":
        "an off control was found that demonstrably suppresses reasoning on "
        "this lane, which rules out the failure mode of having no off switch; "
        "the spelling tried first was accepted and ignored",
    "STREAM_CONTENT_DELTAS":
        "non-empty content deltas were seen, which rules out the failure mode "
        "of the answer arriving only in the reasoning channel",
    "NO_EMPTY_THINK_SHELLS":
        "the assembled prompt contains no <think></think> pair, which is "
        "trap 25's failure mode directly. Scoped to 25: it does NOT clear "
        "trap 04",
    "WRITE_FIELD_IDENTIFIED":
        "a marked prior-turn reasoning string was found in the assembled "
        "prompt, so history reasoning demonstrably survives",
    "WRITE_FIELD_SINGLE":
        "exactly one of the two field names carried the marker through",
    "VALIDATION_REJECTS_UNKNOWN_FIELD":
        "an invented top-level field was rejected while the IDENTICAL request "
        "without it returned 200, so the rejection is attributable to the "
        "field rather than to a lane that rejects everything. That paired "
        "control is the whole verdict: without the 200 baseline this would be "
        "satisfied by a wrong model name or an expired key. Scoped narrowly: "
        "it rules out 'a misspelled or unimplemented parameter is silently "
        "accepted', and it does NOT rule out a known-but-unimplemented field "
        "being accepted and ignored, which stays with traps 03 and 29",
    "TOOL_CHOICE_NONE_BINDS":
        "a control WITH tools and no tool_choice produced a tool call on this "
        "lane, and the identical request with tool_choice none did not, so the "
        "suppression is attributable to the parameter rather than to a model "
        "that was never going to call. Without that control this CLEAN would "
        "be the empty-set shape: 'no call happened' is satisfied by a model "
        "that simply declined",
    "TOOL_CHOICE_REJECTED":
        "the lane returns a non-200 for tool_choice none, so the parameter "
        "cannot be silently accepted and ignored here. Rejecting loudly is the "
        "opposite failure from trap 78 and a safe one",
    "KWARG_UNKNOWN_REJECTED":
        "an invented kwarg alone is rejected while an otherwise identical "
        "control succeeds, so the rejection is attributable to the kwarg",
    "TOOL_CALLS_RETURNED":
        "a structured tool_calls array came back",
    "TOOL_MARKUP_PARSED":
        "no raw <tool_call> markup anywhere in content or reasoning, asserted "
        "on the observed value rather than a fixed word",
    "MODEL_ELECTS_NOT_TO_CALL":
        "the forced control calls while the natural prompt does not, which "
        "separates model choice from broken plumbing",
    "CONTENT_PRESENT_AT_CAP_HIT":
        "the cap was actually reached and content came back anyway, which is "
        "the only single-probe observation that rules empty-at-cap out",
    "GENERATION_CONFIG_PRESENT":
        "the file exists at the compared revision, which is trap 21's failure "
        "mode directly",
    "SAMPLING_DEFAULTS_MATCH":
        "server and checkpoint agree on every key both sides declare, and the "
        "title says the non-shared keys were not compared",
    "MM_REJECTED_NAMING_MODALITY":
        "the server named the modality in its rejection, so 'text-only' is "
        "read off the server rather than assumed (advisory, not a trap)",
    "MM_SURFACE_ACCEPTS_IMAGES":
        "an inline image part was accepted (advisory, not a trap)",
    "MM_USAGE_ATTRIBUTABLE":
        "prompt_tokens_details came back populated (advisory, not a trap)",
    "MM_ORDER_PRESERVED":
        "the two orderings render differently, which rules out order being "
        "discarded (advisory, not a trap)",
    "MM_ERROR_CLASSIFIED_4XX":
        "a bad media path returned 4xx (advisory, not a trap)",
}

# Every scenario flag combination the suite can reach, so the sweep below sees
# every CLEAN the tool is capable of emitting, not only the well-behaved path.
SWEEP = [
    {}, {"props": llamacpp_props(TEMPLATE_WITH_EFFORT)},
    {"props": llamacpp_props(TEMPLATE_WITHOUT_EFFORT)},
    {"reasoning_field": None}, {"reasoning_field": "reasoning"},
    {"thinking_effective": False}, {"explicit_off_honored": False},
    {"explicit_off_honored": False, "props": llamacpp_props()},
    {"explicit_off_honored": False, "anonymous": True},
    {"anonymous": True},
    {"ollama": True, "off_kwarg": "reasoning_effort"},
    {"off_kwarg": "reasoning_effort"},
    {"kwarg_rejection": "unknown"}, {"kwarg_rejection": "known"},
    {"validates_top_level": True},
    {"tool_calls": "never", "tool_choice_supported": True},
    {"tool_choice_none_honored": False},
    {"tool_calls": "never", "tool_choice_supported": False},
    {"tool_calls": "forced_only"}, {"tool_markup": True},
    {"tool_markup_alongside": True},
    {"render": False}, {"preserve_history": False},
    {"accepts_images": False, "image_reject_names_modality": True},
    {"accepts_images": False, "image_reject_names_modality": False},
    {"ceiling": "content"}, {"ceiling": "content_at_cap"},
    {"ceiling": "empty_at_cap"}, {"ceiling": "empty_not_at_cap"},
    {"stream_channel": "reasoning"}, {"stream_channel": None},
    {"bad_media_status": 500}, {"usage_details": None},
]


class TestCleanContract(DoctorVerdictCase):

    def test_every_clean_the_tool_can_emit_is_in_the_contract(self):
        seen = set()
        for flags in SWEEP:
            with FixtureLane(**flags) as base:
                doc = diagnose(base)
            self.check_structure(doc)
            seen |= {f["code"] for f in doc.clean}
        with FixtureHub(HUB_REPOS) as hub, \
                FixtureLane(props=llamacpp_props(temperature=0.6)) as base:
            for repo, rev in (("acme/demo", "v1.0"), ("acme/nvfp4", "main"),
                              ("acme/inconfig", "main")):
                doc = diagnose(base, hf_repo=repo, hf_revision=rev, hub=hub)
                self.check_structure(doc)
                seen |= {f["code"] for f in doc.clean}

        undocumented = seen - set(CLEAN_CONTRACT)
        self.assertFalse(undocumented,
                         f"these CLEAN verdicts are not in CLEAN_CONTRACT: "
                         f"{sorted(undocumented)}. A CLEAN must rule the "
                         f"failure mode OUT, not merely fail to observe it. "
                         f"Write down which failure mode each one rules out, "
                         f"or demote it.")
        # and the table must not rot: nothing listed that can never fire
        stale = set(CLEAN_CONTRACT) - seen
        self.assertFalse(stale,
                         f"CLEAN_CONTRACT lists verdicts no scenario produces: "
                         f"{sorted(stale)}. Either the sweep lost coverage or "
                         f"the verdict is dead code.")

    def test_the_demoted_verdicts_never_come_back(self):
        # Named explicitly so a future refactor that reintroduces any of them
        # fails loudly rather than quietly restoring a false CLEAN.
        for code in ("QUANT_IN_CONFIG_JSON", "QUANT_IN_HF_QUANT_CONFIG",
                     "CONTENT_PRESENT_AT_CEILING", "KWARG_READ_BY_TEMPLATE"):
            self.assertNotIn(code, CLEAN_CONTRACT,
                             f"{code} was demoted from CLEAN by an audit; it "
                             f"must not be readmitted")

    def test_no_clean_carries_a_trap_id_it_cannot_settle(self):
        # Never-clean ids must not appear in a CLEAN, in any scenario.
        for flags in SWEEP:
            with FixtureLane(**flags) as base:
                doc = diagnose(base)
            for f in doc.clean:
                for n in f["traps"]:
                    self.assertNotIn(
                        n, md.TRAPS_NEVER_CLEAN,
                        f"{f['code']} reports CLEAN for trap {n}, which this "
                        f"tool can only observe the label of")


if __name__ == "__main__":
    unittest.main(verbosity=2)
