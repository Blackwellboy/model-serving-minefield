#!/usr/bin/env python3
"""minefield_doctor.py: point it at your OpenAI-compatible endpoint, get a
diagnosis against the model-serving-minefield registry.

    python3 minefield_doctor.py --base-url http://localhost:8000/v1

WHAT THIS IS: a thinking-stack preflight, not a minefield doctor. Its checks
cluster on reasoning fields, chat templates and history assembly, thinking
control kwargs, tool parsing and token ceilings, because that is what a
read-only request-shaped probe can reach. It says nothing about quantisation
kernel paths, container toolchains, memory allocation, MoE routing, eval-harness
confounds or long-context behaviour, which is most of the registry. A run with
no problems is a statement about the trap ids in its clean count, never a bill
of health. Findings print Core tier first within each bucket (see CORE.md).

Safety, up front:
  - READ-ONLY. Never restarts anything, never changes server state, never
    writes to your server. GET probes plus a small, fixed set of chat
    completions (at most 17 generation requests, each capped at 512 output
    tokens; one uses 512, the rest 16 to 256), plus render or tokenise calls
    that generate nothing.
  - The two multimodal probes send a GENERATED 8x8 PNG built in-process from
    the standard library, and one deliberately non-existent file path. No file
    of yours is read and nothing is uploaded.
  - Sends nothing anywhere except your endpoint (and huggingface.co, only
    if you pass --hf-repo, to read a few public config files).
  - Everything it finds cites the registry trap it comes from.

Output, in this order:
    PROBLEMS         something is wrong, with the fix and the trap
    CHECKED AND CLEAN a probe ran AND its result can only mean "clean"
    INCONCLUSIVE     a probe ran, but the result is consistent with several
                     materially different states, so it is not a clean bill
    COULD NOT CHECK  the probe could not run, or its precondition was missing
    COVERAGE         how much of the registry this run actually touched

The distinction between the last three is the whole point of this tool. A
result only reaches CHECKED AND CLEAN when the observation rules out the
failure mode. If acceptance, silence, or a missing template could equally well
explain what was seen, it goes to INCONCLUSIVE or COULD NOT CHECK, never to
CLEAN. Add --report for a markdown block you can paste into an "I hit a trap"
issue, and --json for the machine-readable form, which carries the exact
assertions that ran, not only the prose.

Stdlib only. jinja2 is used for one extra render path if installed; never
required. Exit codes: 0 ran (read the sections), 1 endpoint unreachable.
"""
import argparse, json, re, sys, urllib.request, urllib.error, zlib

REG = "https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps"

# Total numbered entries in the registry. Verified against the trap files in
# traps/*/ at the tip that ships this file; doctor/tests/test_doctor_verdicts.py
# asserts this constant still matches the tree, so it cannot drift silently.
# Any PR that lands new trap files fails that test until this is bumped and the
# coverage sentences in README.md and doctor/README.md are updated with it.
REGISTRY_TRAP_COUNT = 107

TRAP_PATHS = {
    "01": "reasoning/01-reasoning-field-two-names.md",
    "02": "template/02-orphaned-think-close-tag.md",
    "03": "reasoning/03-enable-thinking-default-drift.md",
    "04": "template/04-history-reasoning-stripping.md",
    "07": "reasoning/07-reasoning-effort-silently-ignored.md",
    "10": "quantization/10-quant-label-is-not-the-kernel-path.md",
    "12": "evaluation/12-empty-content-at-token-ceiling.md",
    "16": "evaluation/16-finish-reason-is-not-a-failure-signal.md",
    "17": "evaluation/17-per-arm-recommended-sampling-confound.md",
    "19": "tools/19-missing-jinja-breaks-tool-parsing.md",
    "20": "reasoning/20-reasoning-write-field-name-diverges.md",
    "21": "versioning/21-no-generation-config-server-defaults-win.md",
    "22": "evaluation/22-family-card-budget-floors-differ-by-size.md",
    "23": "reasoning/23-streaming-answer-lands-in-reasoning-channel.md",
    "25": "template/25-empty-think-blocks-poison-prefix-cache.md",
    "26": "tools/26-tool-call-inside-unclosed-think.md",
    "78": "tools/78-tool-choice-accepted-and-ignored.md",
    "29": "reasoning/29-server-reasoning-off-is-not-an-off-switch.md",
    "77": "reasoning/77-only-one-request-field-is-validated.md",
}

# The registry's Core tier (../CORE.md): the twelve entries selected on
# evidence of what has cost people evenings, rather than on which entries have
# the best data. Findings are ordered Core first within each verdict bucket so
# the first lines an operator reads are the ones most likely to matter.
#
# Three of the twelve (35, 53, 61) have no check in this tool and appear
# here only so the ordering key and the coverage line stay honest about that.
# 77 was the fourth until check_request_validation landed: its own entry names
# the two-minute probe as the fix, so implementing it was reading the entry
# rather than inventing a check.
# Keep this set in sync with CORE.md; it is a reading-order tier, not a claim
# about severity in any individual case.
CORE_TRAP_IDS = {"01", "03", "04", "10", "12", "16", "17", "19",
                 "35", "53", "61", "77"}

# Honest sub-classification of the ids above, printed in the coverage block.
# A trap id in TRAP_PATHS does NOT mean an independent check exists for it.
TRAPS_SHARED_HEURISTIC = {
    # decided by the same single render inspection that decides trap 04
    "25": "shares the trap-04 history-render heuristic; no independent probe",
    # annotation on the single trap-12 ceiling finding, not a separate probe
    "16": "annotation on the trap-12 ceiling finding; no independent probe",
    "22": "linked from the ceiling check so you can find the entry, but never "
          "given a verdict by it; see the label-only note below",
}
TRAPS_NEED_HF_REPO = {"10", "17", "21"}
TRAPS_NEED_RENDER_PATH = {"04", "20", "25"}

# Ids this tool reports on that are NOT numbered registry entries. They are
# advisory: real observations with real fixes, but no trap file, no README row
# and no entry a reader can go and check. Printing them beside numbered traps
# without saying so invites the reader to look up a trap that does not exist.
ADVISORY_IDS = {
    "mm-surface": "multimodal surface (does this lane accept media at all)",
    "mm-usage": "media token attribution in the usage block",
    "mm-order": "content-part ordering in the assembled prompt",
    "mm-errors": "how media-fetch failures are classified",
    "mm-audio-video": "audio and video channels, which this tool never probes",
}

# Checks that read a label or a manifest rather than the running engine, so
# they can never reach CLEAN no matter what they find. Declared here so the
# coverage block cannot be read as depth this tool does not have.
TRAPS_NEVER_CLEAN = {
    "10": "the hub check reads the checkpoint's quantisation manifest, which "
          "establishes the LABEL. Trap 10 is about the kernel path the engine "
          "actually took, which needs a runtime tell, so this check can reach "
          "INCONCLUSIVE but never CLEAN",
    "22": "a budget floor is a distribution across sizes and budgets; this "
          "tool sends one request at one budget, so it never reaches a "
          "trap-22 verdict in either direction",
}

# huggingface.co, overridable so the regression suite can point at a fixture
# instead of the live hub. Not a command-line flag on purpose: the safety
# story says "your endpoint and huggingface.co", and that stays true.
HF_BASE = "https://huggingface.co"


def trap(n):
    """Registry link for a trap id. Ids that are not yet numbered in the
    registry (drafts pending a land) resolve to the traps index."""
    p = TRAP_PATHS.get(n)
    return f"{REG}/{p}" if p else REG


RMARK = "ZQXMARK_REASONING_7734"
TOOLS = [{"type": "function", "function": {
    "name": "get_time", "description": "Get current time in a timezone",
    "parameters": {"type": "object",
                   "properties": {"timezone": {"type": "string"}},
                   "required": ["timezone"]}}}]

# ------------------------------------------------------------- transport

def _req(url, key=None, data=None, timeout=60):
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)

def get(url, key=None, timeout=15):
    return _req(url, key, None, timeout)

def post(url, body, key=None, timeout=180):
    return _req(url, key, json.dumps(body).encode(), timeout)

# ------------------------------------------------------------ diagnosis state

def A(claim, observed, held=True):
    """One recorded assertion: what was claimed, what was seen, did it hold.

    Every verdict carries these. A CLEAN with no assertions behind it is a
    bug in this file, and the regression suite fails the build over it.
    """
    return {"assert": claim, "observed": observed,
            "result": "held" if held else "failed"}


class Doc:
    """Verdict accumulator.

    Four levels, borrowed from checks/preflight_template.py so the two tools
    speak one vocabulary:

      PROBLEM       a defect was observed
      OK            observed, and the observation rules out the defect
      INCONCLUSIVE  the probe RAN and returned, but several materially
                    different states produce this same result
      UNKNOWN       the probe could not run, or a precondition was missing
                    (this is preflight_template's NO_RENDER_PATH shape)
    """

    def __init__(self):
        self.findings = []
        self.requests_made = 0
        self.stack, self.model, self.build = "unknown", None, None
        self.evidence = {}

    def _add(self, level, traps, title, code, detail, asserts):
        self.findings.append({"level": level, "code": code, "traps": list(traps),
                              "title": title, "detail": detail,
                              "assertions": list(asserts or [])})

    def problem(self, traps, title, fix, code="PROBLEM", asserts=None):
        self._add("PROBLEM", traps, title, code, fix, asserts)

    def ok(self, traps, title, code="OK", asserts=None):
        self._add("OK", traps, title, code, None, asserts)

    def inconclusive(self, traps, title, why, code="INCONCLUSIVE", asserts=None):
        self._add("INCONCLUSIVE", traps, title, code, why, asserts)

    def skip(self, traps, title, why, code="UNKNOWN", asserts=None):
        self._add("UNKNOWN", traps, title, code, why, asserts)

    # -- views ------------------------------------------------------------
    def by(self, level):
        """Findings at one level, Core-tier first.

        The sort is stable, so within the Core group and within the rest the
        original probe order is preserved. Ordering only; nothing is dropped,
        no verdict changes, and a finding that touches no numbered trap sorts
        with the non-Core group rather than being hidden.
        """
        out = [f for f in self.findings if f["level"] == level]
        out.sort(key=lambda f: 0 if CORE_TRAP_IDS & set(f["traps"]) else 1)
        return out

    @property
    def problems(self): return self.by("PROBLEM")
    @property
    def clean(self): return self.by("OK")
    @property
    def unsure(self): return self.by("INCONCLUSIVE")
    @property
    def blocked(self): return self.by("UNKNOWN")

    def trap_ids(self, level):
        out = set()
        for f in self.by(level):
            out |= {n for n in f["traps"] if n in TRAP_PATHS}
        return out


def chat(doc, base, key, model, messages, **kw):
    body = {"model": model or "default", "messages": messages,
            "temperature": 0, "max_tokens": kw.pop("max_tokens", 128)}
    body.update(kw)
    doc.requests_made += 1
    st, txt = post(base + "/chat/completions", body, key)
    if st != 200:
        return st, None, txt
    try:
        d = json.loads(txt)
        return st, d["choices"][0], d
    except Exception as e:
        return st, None, f"unparseable: {e}"

def msg_fields(choice):
    m = choice["message"]
    return (m.get("content") or "", m.get("reasoning_content") or "",
            m.get("reasoning") or "", m.get("tool_calls") or [], m)

# ------------------------------------------------------------------ checks

def detect_stack(doc, base, root, key):
    st, txt = get(base + "/models", key)
    if st != 200:
        return False
    models_owner = None
    try:
        model_row = json.loads(txt)["data"][0]
        doc.model = model_row["id"]
        models_owner = model_row.get("owned_by")
    except Exception:
        pass
    st, txt = get(root + "/api/version", key, timeout=8)
    if st == 200 and '"version"' in (txt or ""):
        # Ollama. Worth detecting for one specific reason: it does not read
        # chat_template_kwargs at all, so the vLLM spelling below is accepted,
        # silently ignored, and makes every toggle arm fire.
        doc.stack = "ollama"
        try:
            doc.build = str(json.loads(txt).get("version", ""))[:40]
        except Exception:
            pass
        return True
    st, txt = get(root + "/props", key, timeout=8)
    if st == 200:
        doc.stack = "llama.cpp"
        try:
            props = json.loads(txt)
            doc.evidence["props"] = props
            doc.build = (props.get("build_info") or "")[:40]
        except Exception:
            pass
    else:
        # SGLang 0.5.16 has neither /props nor /version, but identifies its
        # model rows. Check that before falling through to the anonymous
        # OpenAI-compatible bucket.
        if models_owner == "sglang":
            doc.stack = "sglang"
        else:
            # mlx server and vLLM both lack /props; tell them apart cheaply
            st2, _ = get(root + "/version", key, timeout=8)
            doc.stack = ("vllm" if st2 == 200
                         else "openai-compatible (vLLM/MLX/other)")
    return True


# Which request field turns thinking on and off is a property of the SERVING
# STACK, not of the model. This tool used to send vLLM's spelling to every
# lane. On a stack that does not read it the kwarg is accepted, ignored, and
# every arm fires -- which is indistinguishable from an off switch that does
# not work, and was reported as exactly that. Measured on Ollama 0.32.5:
# chat_template_kwargs.enable_thinking=false leaves thinking ON (569 chars of
# reasoning) while reasoning_effort=none turns it OFF (0 chars). The old code
# called that lane a trap-03 PROBLEM and, on the same evidence, emitted a
# trap-29 CLEAN asserting no client kwarg could override. Both were wrong.
VLLM_OFF = ("chat_template_kwargs.enable_thinking=false",
            {"chat_template_kwargs": {"enable_thinking": False}})
VLLM_ON = ("chat_template_kwargs.enable_thinking=true",
           {"chat_template_kwargs": {"enable_thinking": True}})
EFFORT_OFF = ("reasoning_effort=none", {"reasoning_effort": "none"})
EFFORT_ON = ("reasoning_effort=high", {"reasoning_effort": "high"})

# Stacks whose thinking-off spelling we have established first-hand. Only for
# these may "the off switch does not work" be asserted from a firing off arm:
# anywhere else, a firing off arm is equally consistent with having sent a
# name the stack never reads.
STACKS_WITH_KNOWN_OFF_CONTROL = {"vllm", "llama.cpp", "ollama", "sglang"}


def on_control_for(stack):
    return EFFORT_ON if stack == "ollama" else VLLM_ON


def off_controls_for(stack):
    """Off controls to try, the stack's own spelling first.

    The alternates are tried too, because a control that actually suppresses is
    positive evidence about THIS lane no matter which stack we guessed.
    """
    return [EFFORT_OFF, VLLM_OFF] if stack == "ollama" else [VLLM_OFF, EFFORT_OFF]


def check_reasoning_fields(doc, base, key):
    """Traps 01 (read side), 02 (orphan close), 03 (toggle map), 29 (override)."""
    arms = {}
    on_label, on_body = on_control_for(doc.stack)
    off_tries = off_controls_for(doc.stack)
    off_label, off_body = off_tries[0]
    doc.evidence["thinking_controls"] = {
        "stack": doc.stack, "on": on_label,
        "off_tried_in_order": [lbl for lbl, _ in off_tries]}
    for name, body_kw in (("on", on_body),
                          ("off", off_body),
                          ("absent", {})):
        st, choice, raw = chat(doc, base, key, doc.model,
                               [{"role": "user", "content":
                                 "Which is larger, 17*24 or 400? Answer briefly."}],
                               max_tokens=256, **body_kw)
        if st != 200 or choice is None:
            arms[name] = {"error": f"http {st}"}
            continue
        c, rc, rr, _tc, m = msg_fields(choice)
        arms[name] = {
            "content_len": len(c),
            "reasoning_content": len(rc), "reasoning": len(rr),
            "think_in_content": "<think>" in c or "</think>" in c,
            "stray_close": c.lstrip().startswith("</think>"),
            "keys": sorted(m.keys()), "finish": choice.get("finish_reason")}
    doc.evidence["toggle_arms"] = arms
    live = {k: v for k, v in arms.items() if "error" not in v}
    if not live:
        doc.skip(["01", "02", "03", "29"],
                 "reasoning field, orphan-tag, thinking-toggle and gate checks",
                 f"all three probe requests failed ({arms['on'].get('error')})",
                 code="ALL_ARMS_FAILED",
                 asserts=[A("at least one toggle arm returns HTTP 200",
                            {k: v.get("error") for k, v in arms.items()}, held=False)])
        return

    on = arms.get("on", {})
    fields = [k for k in ("reasoning_content", "reasoning") if on.get(k)]
    if fields:
        doc.ok(["01"], f"reasoning exposed under {' and '.join(fields)} "
               f"(read that exact name; the other name may not exist here)",
               code="REASONING_FIELD_IDENTIFIED",
               asserts=[A("thinking-on response carries a non-empty reasoning field",
                          {k: on.get(k) for k in ("reasoning_content", "reasoning")})])
    elif on.get("think_in_content"):
        doc.problem(["01"], "reasoning arrives as <think> tags inside content, "
                    "not as a separate field: any harness reading only a "
                    "reasoning field scores this lane as never thinking",
                    "parse think tags from content on this lane, or enable the "
                    "server's reasoning parser",
                    code="REASONING_IN_CONTENT",
                    asserts=[A("thinking-on content contains think tags",
                               on.get("content_len"))])
    elif "error" not in on:
        # The old code called this CLEAN. It is not. Six materially different
        # states produce "no reasoning field, no think tags, HTTP 200", and
        # this probe cannot tell them apart. Trap 07's own rule (acceptance
        # proves nothing) applies to silence as well.
        doc.skip(["01"], "reasoning read-field identification",
                 "with thinking requested ON the response carried no reasoning "
                 "field and no think tags. That single observation is produced "
                 "by at least six materially different states, and this probe "
                 "distinguishes none of them: (1) a genuinely non-reasoning "
                 "model, (2) the enable_thinking kwarg accepted and ignored, "
                 "(3) the server's reasoning parser not enabled so the trace "
                 "was discarded, (4) the chat template not reading this kwarg "
                 "at all, (5) reasoning emitted on a third channel this tool "
                 "does not read, (6) a genuine server-side gate. Determine "
                 "which before reporting this lane as non-thinking: enumerate "
                 "the kwargs the template reads with "
                 "checks/preflight_template.py --template-file, and check the "
                 "server's reasoning-parser flag.",
                 code="THINKING_ON_NO_REASONING",
                 asserts=[A("thinking-on response carries reasoning_content, "
                            "reasoning, or think tags in content",
                            {"reasoning_content": on.get("reasoning_content"),
                             "reasoning": on.get("reasoning"),
                             "think_in_content": on.get("think_in_content"),
                             "message_keys": on.get("keys")}, held=False)])

    # -- trap 02, scoped to the arms that actually answered ----------------
    stray = [n for n, a in live.items() if a.get("stray_close")]
    if stray:
        doc.problem(["02"], f"response content starts with a stray </think> "
                    f"({', '.join(stray)} arm): parser strips the open tag but "
                    f"not the close",
                    "fix the reasoning-parser pairing; strip the orphan before "
                    "scoring anything",
                    code="ORPHANED_CLOSE_THINK",
                    asserts=[A("no returned arm starts with </think>", stray,
                               held=False)])
    elif len(live) == len(arms):
        doc.ok(["02"], "no orphaned </think> at the start of any of the three "
               "probe responses",
               code="NO_ORPHANED_CLOSE_THINK",
               asserts=[A("no returned arm starts with </think>",
                          sorted(live))])
    else:
        doc.inconclusive(["02"], "orphaned </think> at content start",
                         f"clean in the {len(live)} arm(s) that returned "
                         f"({', '.join(sorted(live))}), but "
                         f"{len(arms) - len(live)} arm(s) failed and were never "
                         f"inspected. An orphan that only appears under the "
                         f"unexamined arm would not have been seen.",
                         code="ORPHAN_CHECK_PARTIAL",
                         asserts=[A("all three arms inspected for a leading "
                                    "</think>", sorted(live), held=False)])

    # -- traps 03 and 29 ---------------------------------------------------
    def fired(a):
        return bool(a.get("reasoning_content") or a.get("reasoning")
                    or a.get("think_in_content"))

    if len(live) < 3:
        doc.skip(["03", "29"], "thinking-toggle map and server-side gate",
                 f"the map needs all three arms (explicit on, explicit off, "
                 f"kwarg absent); {len(arms) - len(live)} failed",
                 code="TOGGLE_ARMS_INCOMPLETE",
                 asserts=[A("all three toggle arms returned", sorted(live),
                            held=False)])
        return

    f_on, f_off, f_abs = fired(on), fired(arms["off"]), fired(arms["absent"])

    # If the primary off control did not suppress, try the other spellings we
    # know before concluding anything. A control that suppresses settles the
    # question by observation and outranks any guess from stack detection.
    working_off = None if f_off else off_label
    alt_results = {}
    if f_off:
        for lbl, body in off_tries[1:]:
            st, choice, _raw = chat(doc, base, key, doc.model,
                                    [{"role": "user", "content":
                                      "Which is larger, 17*24 or 400? Answer briefly."}],
                                    max_tokens=256, **body)
            if st != 200 or choice is None:
                alt_results[lbl] = f"http {st}"
                continue
            c, rc, rr, _tc, _m = msg_fields(choice)
            a_fired = bool(rc or rr or "<think>" in c or "</think>" in c)
            alt_results[lbl] = {"fired": a_fired}
            if not a_fired:
                working_off = lbl
                break
        doc.evidence["off_control_alternates"] = alt_results
    doc.evidence["working_off_control"] = working_off
    # Established = we can name the control this lane reads, either because one
    # demonstrably suppressed, or because the detected stack's own documented
    # spelling is what we sent.
    off_established = bool(working_off) or doc.stack in STACKS_WITH_KNOWN_OFF_CONTROL
    doc.evidence["toggle_fired"] = {"on": f_on, "off": f_off, "absent": f_abs}
    if not (f_on or f_off or f_abs):
        # A toggle map in which nothing ever fires is not a map. Reporting
        # "on=False, off=False, absent lands off-like" as CLEAN told operators
        # their toggle was characterised when in fact no arm produced any
        # observable, so no arm could be told apart from any other.
        doc.skip(["03", "29"], "thinking-toggle map and server-side gate",
                 "no arm produced any reasoning observable at all, so the three "
                 "arms are indistinguishable and the toggle is uncharacterised. "
                 "This is the same silence as the read-field check above and has "
                 "the same six candidate causes; resolve that one first.",
                 code="TOGGLE_MAP_VACUOUS",
                 asserts=[A("at least one toggle arm produces a reasoning "
                            "observable", {"on": f_on, "off": f_off,
                                           "absent": f_abs}, held=False)])
        return

    landing = ("on-like" if f_abs == f_on and f_on else
               ("off-like" if f_abs == f_off else "distinct"))
    if f_off and working_off:
        # The spelling we tried first is not the one this lane reads, but a
        # control that does exist was found. This is NOT trap 03's defect: the
        # lane has a working off switch, under a different name.
        doc.ok(["03"], f"thinking toggle map: {off_label} does NOT turn "
               f"thinking off on this lane, but {working_off} does. "
               f"explicit-on fired, explicit-off under {working_off} did not, "
               f"absent lands {landing}. Use {working_off} here, and treat the "
               f"other spelling as accepted-and-ignored rather than as an off "
               f"switch",
               code="OFF_CONTROL_IS_A_DIFFERENT_KWARG",
               asserts=[A("the explicit-on arm fires", {"on": f_on}),
                        A(f"an off control was found that suppresses reasoning",
                          {"control": working_off, "alternates": alt_results}),
                        A("the first-tried spelling did not suppress",
                          {"tried": off_label, "fired": f_off})])
    elif f_off and not off_established:
        # Every off control we know fired, but the stack was never identified,
        # so we cannot say we sent the name it reads. "The off switch is
        # broken" and "we used the wrong word" produce this identical
        # observation. Calling it a PROBLEM here is the false positive this
        # tool produced against Ollama.
        doc.skip(["03"], "thinking-toggle map",
                 f"reasoning fired on every arm including explicit-off, but "
                 f"the stack behind this endpoint was not identified "
                 f"(detected: {doc.stack!r}), so the off control it reads is "
                 f"unknown. Tried "
                 f"{', '.join(lbl for lbl, _ in off_tries)}; none suppressed. "
                 f"A lane that ignores the kwarg you sent is indistinguishable "
                 f"from a lane whose off switch does not work, and this tool "
                 f"cannot tell them apart without knowing the stack. Enumerate "
                 f"the kwargs the template actually reads with "
                 f"checks/preflight_template.py --template-file, or name the "
                 f"stack, before treating this lane as having no off switch.",
                 code="OFF_CONTROL_NAME_NOT_ESTABLISHED",
                 asserts=[A("the off control this lane reads is known",
                            {"stack": doc.stack,
                             "tried": [lbl for lbl, _ in off_tries],
                             "alternates": alt_results}, held=False)])
        # deliberately NOT a return: trap 29 gets its own verdict below, from
        # its own gate. Returning here made that gate unreachable, and a
        # mutation run proved the test protecting it passed for the wrong
        # reason -- the code it was meant to exercise never ran.
    elif f_off:
        # An explicit off that still produces reasoning is the defect trap 03
        # is about, and the old code reported it as a characterised map. A map
        # is not a clean bill: it described the arms and then filed the
        # description under CHECKED AND CLEAN even when the off arm fired.
        doc.problem(["03"], f"explicit-off still produces reasoning: the arm "
                    f"sent with enable_thinking=false fired anyway "
                    f"(on={f_on}, off={f_off}, absent lands {landing}). The "
                    f"off switch on this lane does not turn thinking off, so "
                    f"every 'non-thinking' budget, latency and cost number "
                    f"taken here was measured on a thinking lane",
                    "do not treat enable_thinking=false as an off state on "
                    "this lane. Find the kwarg the template actually reads "
                    "(checks/preflight_template.py --template-file), or gate "
                    "thinking server-side, and re-take any number that assumed "
                    "the off arm was off",
                    code="EXPLICIT_OFF_STILL_FIRES",
                    asserts=[A("the explicit-off arm produces no reasoning "
                               "observable",
                               {"on": f_on, "off": f_off, "absent": f_abs,
                                "controls_tried": [lbl for lbl, _ in off_tries],
                                "stack": doc.stack},
                               held=False)])
    elif f_on:
        doc.ok(["03"], f"thinking toggle map: explicit-on fired, explicit-off "
               f"did not, absent lands {landing}. The two explicit arms are "
               f"separable and the off arm is genuinely off. Send the kwarg "
               f"explicitly: the absent arm is revision- and server-dependent "
               f"and this run says only where it landed today, not that "
               f"leaving it out is safe",
               code="TOGGLE_MAP_CHARACTERISED",
               asserts=[A("the explicit-on arm fires", {"on": f_on}),
                        A("the explicit-off arm does not fire", {"off": f_off}),
                        A("the kwarg-absent arm was observed and classified",
                          {"absent": f_abs, "lands": landing})])
    else:
        # Something fired (checked above) but not the explicit-on arm, so the
        # toggle has no positive control and the map cannot be read as one.
        doc.inconclusive(["03"], "thinking-toggle map",
                         f"a reasoning observable appeared on this lane, but "
                         f"NOT on the explicit-on arm (on={f_on}, off={f_off}, "
                         f"absent={f_abs}). Without the on arm firing there is "
                         f"no positive control, so which kwarg value produces "
                         f"which state cannot be read off these three arms. "
                         f"Enumerate the kwargs the template actually reads "
                         f"with checks/preflight_template.py --template-file "
                         f"before describing this lane's toggle.",
                         code="TOGGLE_MAP_NO_POSITIVE_CONTROL",
                         asserts=[A("the explicit-on arm fires (positive "
                                    "control)", {"on": f_on, "off": f_off,
                                                 "absent": f_abs}, held=False)])

    if f_on and not f_abs:
        doc.problem(["29"], "server-side default has thinking off, but a "
                    "client kwarg re-enables it per request: the flag is a "
                    "default, not a gate, and thinking requests can blow "
                    "non-thinking token budgets",
                    "strip or deny thinking kwargs at your gateway, or size "
                    "max_tokens for the thinking distribution",
                    code="SERVER_OFF_IS_NOT_A_GATE",
                    asserts=[A("kwarg-absent arm fires whenever explicit-on "
                               "fires", {"on": f_on, "absent": f_abs},
                               held=False)])
    elif f_abs and off_established:
        doc.ok(["29"], f"thinking already fires with no kwarg sent, so there is "
               f"no server-side off state for a client kwarg to override on "
               f"this lane. The client-side control that does work here is "
               f"{working_off or off_label}",
               code="NO_SERVER_SIDE_OFF_STATE",
               asserts=[A("kwarg-absent arm fires", {"absent": f_abs}),
                        A("the client off control this lane reads is known, so "
                          "the claim about client kwargs is not made from "
                          "silence",
                          {"control": working_off or off_label,
                           "stack": doc.stack})])
    elif f_abs:
        # The absent arm firing is a real observation, but the sentence this
        # CLEAN used to make is about CLIENT KWARGS, and we do not know which
        # kwarg this lane reads. Asserting that none can override, having tried
        # only names we guessed, is a clean earned from silence.
        doc.skip(["29"], "server-side thinking gate",
                 f"thinking fires with no kwarg sent, so the server default is "
                 f"on -- but the stack was not identified (detected: "
                 f"{doc.stack!r}) and no off control we tried suppressed, so "
                 f"whether a client kwarg can override cannot be stated. That "
                 f"is a claim about client kwargs and it needs the name this "
                 f"lane reads.",
                 code="SERVER_GATE_CONTROL_UNKNOWN",
                 asserts=[A("the client off control this lane reads is known",
                            {"stack": doc.stack,
                             "tried": [lbl for lbl, _ in off_tries]},
                            held=False)])
    else:
        doc.inconclusive(["29"], "server-side thinking gate",
                         "explicit-on did not fire either, so there is no "
                         "positive control: whether a client kwarg can "
                         "override a server-side off cannot be told from a "
                         "lane where the kwarg never demonstrably worked.",
                         code="GATE_NO_POSITIVE_CONTROL",
                         asserts=[A("explicit-on arm fires (positive control)",
                                    {"on": f_on}, held=False)])


def check_streaming(doc, base, key):
    """Trap 23: streamed answer must land in content."""
    body = {"model": doc.model or "default",
            "messages": [{"role": "user", "content": "Capital of Norway? One word."}],
            "stream": True, "max_tokens": 64, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}}
    doc.requests_made += 1
    try:
        req = urllib.request.Request(base + "/chat/completions",
                                     json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        keys = {}
        with urllib.request.urlopen(req, timeout=120) as r:
            for line in r:
                line = line.decode("utf-8", "replace").strip()
                if not line.startswith("data: {"):
                    continue
                delta = json.loads(line[6:])["choices"][0].get("delta", {})
                for k, v in delta.items():
                    if v:
                        keys[k] = keys.get(k, 0) + 1
        doc.evidence["stream_delta_keys"] = keys
        if keys.get("content"):
            doc.ok(["23"], f"streamed answer arrives in content deltas ({keys})",
                   code="STREAM_CONTENT_DELTAS",
                   asserts=[A("at least one non-empty content delta", keys)])
        elif keys.get("reasoning") or keys.get("reasoning_content"):
            doc.problem(["23"], f"streamed answer arrives ONLY in reasoning deltas "
                        f"with thinking off ({keys}): clients that concatenate "
                        f"content see blank replies",
                        "upgrade the engine (vLLM: past PR #40820) or read "
                        "reasoning deltas as a fallback channel",
                        code="STREAM_ANSWER_IN_REASONING",
                        asserts=[A("at least one non-empty content delta", keys,
                                   held=False)])
        else:
            doc.skip(["23"], "streaming delta placement", "no non-empty deltas seen",
                     code="STREAM_NO_DELTAS",
                     asserts=[A("stream produced non-empty deltas", keys,
                                held=False)])
    except Exception as e:
        doc.skip(["23"], "streaming delta placement", f"stream failed: {e}",
                 code="STREAM_FAILED",
                 asserts=[A("stream request completed", str(e), held=False)])


def _vllm_render(doc, root, key, messages, kwargs):
    """vLLM's assembled prompt, via /v1/chat/completions/render + /detokenize.

    vLLM has exposed a render route since 0.20.0. It returns token ids rather
    than text, so it needs a second call to be readable. Without this path the
    doctor reported "no render path on this stack" on every vLLM lane and
    skipped traps 04, 20 and 25, which is where the worst findings on this
    family came from.

    Falls back to /tokenize with per-token strings, which some builds answer
    even when the route listing does not advertise it.
    """
    body = {"model": doc.model, "messages": messages, "max_tokens": 1}
    if kwargs:
        body["chat_template_kwargs"] = kwargs
    st, txt = post(root + "/v1/chat/completions/render", body, key, timeout=30)
    if st == 200:
        try:
            ids = json.loads(txt).get("token_ids")
            if ids:
                st2, txt2 = post(root + "/detokenize",
                                 {"model": doc.model, "tokens": ids}, key, timeout=30)
                if st2 == 200:
                    d = json.loads(txt2)
                    prompt = d.get("prompt", d.get("text"))
                    if prompt is not None:
                        return prompt, "server /v1/chat/completions/render + /detokenize"
        except Exception:
            pass
    # fallback: tokenise with per-token strings and reassemble
    tb = {"model": doc.model, "messages": messages,
          "add_generation_prompt": True, "return_token_strs": True}
    if kwargs:
        tb["chat_template_kwargs"] = kwargs
    st, txt = post(root + "/tokenize", tb, key, timeout=30)
    if st == 200:
        try:
            strs = json.loads(txt).get("token_strs")
            if strs:
                # byte-level BPE markers: G-with-dot is a space, C-with-dot a newline
                joined = "".join(strs)
                joined = joined.replace("Ġ", " ").replace("Ċ", "\n")
                return joined, "server /tokenize (token_strs)"
        except Exception:
            pass
    return None, None


def render_paths(doc, root, key, messages, kwargs):
    """Return (prompt, how): llama.cpp /apply-template, vLLM render, or jinja2."""
    if doc.stack == "llama.cpp":
        body = {"messages": messages}
        if kwargs:
            body["chat_template_kwargs"] = kwargs
        st, txt = post(root + "/apply-template", body, key, timeout=30)
        if st == 200:
            try:
                return json.loads(txt).get("prompt", ""), "server /apply-template"
            except Exception:
                pass
    else:
        prompt, how = _vllm_render(doc, root, key, messages, kwargs)
        if prompt is not None:
            return prompt, how
    tpl = (doc.evidence.get("props") or {}).get("chat_template")
    if tpl:
        try:
            from jinja2 import Environment, BaseLoader
            env = Environment(loader=BaseLoader())
            env.globals["raise_exception"] = lambda m: ""
            env.globals["strftime_now"] = lambda fmt: ""
            return env.from_string(tpl).render(
                messages=messages, add_generation_prompt=True,
                bos_token="", eos_token="", **(kwargs or {})), "local jinja2"
        except Exception:
            pass
    return None, None


def check_history_assembly(doc, root, key):
    """Traps 04 (stripping), 25 (empty shells), 20 (write field), 02 (tag balance)."""
    def msgs(field):
        turns = [{"role": "system", "content": "You are a coding agent."}]
        for i in (1, 2):
            turns.append({"role": "user", "content": f"Step {i}: what next?"})
            a = {"role": "assistant", "content": f"Doing step {i}."}
            if field:
                a[field] = f"{RMARK} thinking about step {i}."
            turns.append(a)
        turns.append({"role": "user", "content": "Step 3: what next?"})
        return turns

    base_render, how = render_paths(doc, root, key, msgs(None), {"enable_thinking": True})
    if base_render is None:
        doc.skip(["04", "25", "20"], "assembled-prompt inspection at turn 3",
                 "no render path on this stack (tried llama.cpp /apply-template, "
                 "vLLM /v1/chat/completions/render plus /detokenize, vLLM "
                 "/tokenize with token_strs, and a local jinja2 render of a "
                 "server-published template); run the registry's "
                 "checks/preflight_template.py with --template-file instead",
                 code="NO_RENDER_PATH",
                 asserts=[A("a render path returns the assembled prompt",
                            "all four render paths returned nothing",
                            held=False)])
        return
    doc.evidence["render_path"] = how
    empty_pairs = len(re.findall(r"<think>\s*</think>", base_render))
    if empty_pairs:
        doc.problem(["04", "25"], f"history renders {empty_pairs} empty think "
                    f"block(s) for prior turns (via {how}): multi-turn thinking "
                    f"collapse reads as a model property, and equivalent "
                    f"histories cache-miss",
                    "resend prior reasoning under the field this runtime reads, "
                    "or use a template that skips empty wrappers",
                    code="EMPTY_THINK_SHELLS",
                    asserts=[A("assembled turn-3 prompt contains no <think></think> "
                               "pair", empty_pairs, held=False)])
    else:
        # Tagged 25 only. The absence of empty think shells rules out trap 25,
        # which IS about the empty wrappers. It does not rule out trap 04:
        # a lane that drops prior reasoning and emits no wrapper at all leaves
        # exactly this render, and that is the HISTORY_STRIPPED_NO_GATE case
        # decided by the write-field probe below. Trap 04 gets its verdict
        # there, from evidence that can actually settle it.
        doc.ok(["25"], f"no empty think shells in the turn-3 render (via {how})",
               code="NO_EMPTY_THINK_SHELLS",
               asserts=[A("assembled turn-3 prompt contains no <think></think> "
                          "pair", empty_pairs)])

    hits = {}
    for field in ("reasoning_content", "reasoning"):
        r, _ = render_paths(doc, root, key, msgs(field), {"enable_thinking": True})
        hits[field] = (r is not None and RMARK in r)
    doc.evidence["write_field_hits"] = hits
    live = [f for f, h in hits.items() if h]
    if live:
        doc.ok(["20", "04"], f"prior-turn reasoning survives history when resent "
               f"as {' and '.join(live)}; dead write name(s): "
               f"{[f for f, h in hits.items() if not h] or 'none'}. Use the live name",
               code="WRITE_FIELD_IDENTIFIED",
               asserts=[A("a marked prior-turn reasoning string reaches the "
                          "assembled prompt under at least one field name", hits)])
        if len(live) == 1:
            doc.ok(["20"], f"write field on this runtime is {live[0]} only: "
                   f"porting a fix that resends the other name silently does nothing",
                   code="WRITE_FIELD_SINGLE",
                   asserts=[A("exactly one of the two field names survives", hits)])
    else:
        # No field name works on its own, so the template is gating history
        # reasoning behind a kwarg. Try every preservation kwarg shape we have
        # seen in the wild, in both polarities, under both field names. The
        # polarity matters: `preserve_thinking: true` and
        # `truncate_history_thinking: false` are the same switch written two
        # ways, and a pipeline standardised on the first silently no-ops on a
        # family that reads the second.
        gates = [("preserve_thinking", True), ("truncate_history_thinking", False),
                 ("keep_thinking", True), ("include_reasoning", True)]
        found = None
        for gate, val in gates:
            for field in ("reasoning", "reasoning_content"):
                r, _ = render_paths(doc, root, key, msgs(field),
                                    {"enable_thinking": True, gate: val})
                if r is not None and RMARK in r:
                    found = (gate, val, field)
                    break
            if found:
                break
        doc.evidence["preservation_gate"] = found
        if found:
            gate, val, field = found
            doc.problem(["04"], f"history reasoning is stripped by DEFAULT on this "
                        f"lane. The working preservation path is "
                        f"chat_template_kwargs {{{gate!r}: {str(val).lower()}}} "
                        f"WITH prior reasoning resent under {field!r}. Every client "
                        f"that does not set both runs the stripped arm",
                        f"send {gate}={str(val).lower()} and resend reasoning as "
                        f"{field} on every multi-turn call, and record it beside "
                        f"your numbers; do not port a different kwarg name or "
                        f"polarity from another model's writeup",
                        code="HISTORY_STRIPPED_GATE_FOUND",
                        asserts=[A("prior reasoning reaches the prompt with no "
                                   "preservation kwarg", hits, held=False),
                                 A("a known preservation kwarg restores it",
                                   {"gate": gate, "value": val, "field": field})])
        else:
            doc.problem(["04", "20"], "resent prior reasoning under BOTH field "
                        "names, and under four known preservation kwargs, never "
                        "reaches the assembled prompt: this lane strips history "
                        "reasoning with no preservation path this tool knows",
                        "enumerate the kwargs your template actually reads "
                        "(checks/preflight_template.py) before trusting any "
                        "multi-turn number from this lane; the switch may exist "
                        "under a name not in this list",
                        code="HISTORY_STRIPPED_NO_GATE",
                        asserts=[A("prior reasoning reaches the prompt under "
                                   "either field name", hits, held=False),
                                 A("any of four known preservation kwargs "
                                   "restores it",
                                   [g for g, _ in gates], held=False)])

    o, c = base_render.count("<think>"), base_render.count("</think>")
    if c > o:
        doc.problem(["02"], f"assembled prompt has {c} </think> vs {o} <think>: "
                    "orphaned close tags in history",
                    "fix template or history assembly",
                    code="ORPHANED_CLOSE_IN_RENDER",
                    asserts=[A("assembled prompt has no excess </think>",
                               {"open": o, "close": c}, held=False)])


def _tiny_png():
    """An 8x8 grey PNG built from the standard library, base64 encoded.

    Embedding a blob would be shorter, but a constructed one is auditable: you
    can read the chunk assembly and see that nothing is being smuggled into the
    request.
    """
    import base64, struct
    w = h = 8
    raw = b"".join(b"\x00" + bytes([128] * (w * 3)) for _ in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    return base64.b64encode(png).decode()


def _img_part():
    return {"type": "image_url",
            "image_url": {"url": "data:image/png;base64," + _tiny_png()}}


def check_multimodal(doc, base, root, key):
    """Multimodal surface. Traps 12/16 (ceiling with media) plus the multimodal
    family that has no registry numbers yet.

    Before this existed the doctor sent no media at all, so it reported a full
    set of clean checks on a multimodal lane while several multimodal defects
    were live. Reporting clean on a surface you never touched is worse than
    reporting nothing, so this check either exercises the surface or says
    explicitly that it could not.
    """
    txt_part = {"type": "text", "text": "Reply with the single word OK."}
    st, choice, body = chat(doc, base, key, doc.model,
                            [{"role": "user", "content": [txt_part, _img_part()]}],
                            max_tokens=16)
    if st != 200:
        blob = str(body).lower()
        named = [s for s in ("multimodal", "image", "not support", "unsupported",
                             "no multi", "modality") if s in blob]
        if named:
            doc.ok(["mm-surface"], f"text-only lane: the server rejected an inline "
                   f"image part with http {st}, naming the modality, so the "
                   f"multimodal traps do not apply here (this is a checked "
                   f"result, not an assumption)",
                   code="MM_REJECTED_NAMING_MODALITY",
                   asserts=[A("image request rejected with a modality-naming "
                              "error", {"status": st, "matched": named})])
        else:
            doc.skip(["mm-surface"], "multimodal surface",
                     f"an image request failed with http {st} for a reason that "
                     f"does not name multimodality, so whether this lane accepts "
                     f"media is UNKNOWN. Do not read the other clean results as "
                     f"covering media.",
                     code="MM_SURFACE_UNKNOWN",
                     asserts=[A("image-request failure names the modality",
                                {"status": st}, held=False)])
        return

    doc.ok(["mm-surface"], "lane accepts inline image parts (probed with a "
           "generated 8x8 PNG, not assumed from the model name)",
           code="MM_SURFACE_ACCEPTS_IMAGES",
           asserts=[A("inline image part accepted", {"status": st})])

    # ---- usage attribution: can you tell what the media cost you?
    usage = (body or {}).get("usage") if isinstance(body, dict) else None
    if isinstance(usage, dict):
        if usage.get("prompt_tokens_details") in (None, {}):
            doc.problem(["mm-usage"], "prompt_tokens_details is null on a request "
                        "that carried an image: media token cost is not "
                        "attributable from the API, and neither are cache hits",
                        "measure media cost by differencing prompt_tokens against "
                        "a text-only control; do not trust a per-modality "
                        "breakdown you did not measure",
                        code="MM_USAGE_UNATTRIBUTABLE",
                        asserts=[A("usage.prompt_tokens_details is populated",
                                   usage.get("prompt_tokens_details"), held=False)])
        else:
            doc.ok(["mm-usage"], "prompt_tokens_details is populated: media token "
                   "cost is attributable from the usage block",
                   code="MM_USAGE_ATTRIBUTABLE",
                   asserts=[A("usage.prompt_tokens_details is populated",
                              usage.get("prompt_tokens_details"))])
    else:
        doc.skip(["mm-usage"], "media token attribution",
                 "the response carried no usage block at all, so whether media "
                 "cost is attributable could not be determined",
                 code="MM_USAGE_NO_BLOCK",
                 asserts=[A("response carries a usage object", type(usage).__name__,
                            held=False)])

    # ---- part ordering: does the server preserve where the media sat?
    a, how_a = render_paths(doc, root, key,
                            [{"role": "user", "content": [
                                {"type": "text", "text": "ALPHAMARKERZQX"},
                                _img_part(),
                                {"type": "text", "text": "OMEGAMARKERZQX"}]}],
                            {"enable_thinking": True})
    b, _ = render_paths(doc, root, key,
                        [{"role": "user", "content": [
                            _img_part(),
                            {"type": "text", "text": "ALPHAMARKERZQX"},
                            {"type": "text", "text": "OMEGAMARKERZQX"}]}],
                        {"enable_thinking": True})
    if a is None or b is None:
        doc.skip(["mm-order"], "multimodal content-part ordering",
                 "no render path available for the ordering comparison",
                 code="MM_ORDER_NO_RENDER_PATH",
                 asserts=[A("both orderings render", {"a": a is not None,
                                                      "b": b is not None},
                            held=False)])
    elif a == b:
        doc.problem(["mm-order"], "the assembled prompt is byte-identical whether "
                    "the image is sent before or after the text: content-part "
                    "ORDER IS DISCARDED, so prompts that place instructions "
                    "around an image do not reach the model that way",
                    "do not rely on part order; put positional instructions in "
                    "the text itself, and re-check any result that assumed the "
                    "model saw your arrangement",
                    code="MM_ORDER_DISCARDED",
                    asserts=[A("the two part orderings render differently",
                               "byte-identical", held=False)])
    else:
        doc.ok(["mm-order"], "content-part order is preserved in the assembled "
               f"prompt (the two orderings render differently, via {how_a})",
               code="MM_ORDER_PRESERVED",
               asserts=[A("the two part orderings render differently",
                          {"a_chars": len(a), "b_chars": len(b),
                           "identical": False})])
        if "ALPHAMARKERZQXOMEGAMARKERZQX" in a.replace(" ", ""):
            doc.problem(["mm-order"], "adjacent text parts are concatenated with "
                        "no separator in the assembled prompt: words run together",
                        "insert your own whitespace between adjacent text parts",
                        code="MM_TEXT_PARTS_GLUED",
                        asserts=[A("adjacent text parts are separated in the "
                                   "render", "markers adjacent", held=False)])

    # ---- error classification: is a caller mistake reported as a server fault?
    st2, _, body2 = chat(doc, base, key, doc.model,
                         [{"role": "user", "content": [
                             {"type": "text", "text": "Describe it."},
                             {"type": "image_url", "image_url": {
                                 "url": "file:///nonexistent/zqx-doctor-probe.png"}}]}],
                         max_tokens=16)
    if st2 is None:
        doc.skip(["mm-errors"], "media error classification", "probe request failed",
                 code="MM_ERROR_PROBE_FAILED",
                 asserts=[A("bad-media-path probe returned a status", st2,
                            held=False)])
    elif 500 <= st2 < 600:
        doc.problem(["mm-errors"], f"a media path that does not exist is reported "
                    f"as http {st2}, a server fault, not a 4xx caller error",
                    "retry logic keyed on 5xx will retry forever against a "
                    "permanently bad path; classify media-fetch failures "
                    "client-side before retrying, and do not page on them",
                    code="MM_ERROR_MISCLASSIFIED_5XX",
                    asserts=[A("a bad media path returns 4xx", st2, held=False)])
    elif 400 <= st2 < 500:
        doc.ok(["mm-errors"], f"a bad media path is correctly reported as http "
               f"{st2}, a caller error",
               code="MM_ERROR_CLASSIFIED_4XX",
               asserts=[A("a bad media path returns 4xx", st2)])
    else:
        doc.problem(["mm-errors"], f"a media path that does not exist returned "
                    f"http {st2} rather than an error at all",
                    "assert on media resolution client-side; this lane will "
                    "answer a prompt whose media never loaded",
                    code="MM_ERROR_NOT_REPORTED",
                    asserts=[A("a bad media path returns an error status", st2,
                               held=False)])

    # ---- say plainly what was NOT touched
    doc.skip(["mm-audio-video"], "audio and video channels",
             "this doctor sends a generated still image only. Audio and video "
             "paths, their decoders, their error classes and their token costs "
             "are NOT covered by any result above. On a lane that advertises "
             "them, treat the clean results here as scoped to text and images.",
             code="MM_AUDIO_VIDEO_NOT_PROBED",
             asserts=[A("audio or video was probed", "no audio or video request "
                        "is made by this tool", held=False)])


def check_kwarg_deadness(doc, base, root, key):
    """Trap 07: accepted-but-unread kwargs.

    Trap 07's own rule is that API acceptance proves nothing about effect. The
    only thing that turns acceptance into a verdict is reading the template. So
    when no template is readable, the honest answer is COULD NOT CHECK, not the
    CLEAN this used to emit. Likewise a rejection only means "dead knobs are
    loud here" if an otherwise identical request WITHOUT the kwargs succeeds;
    otherwise the rejection is about something else entirely.
    """
    tpl = (doc.evidence.get("props") or {}).get("chat_template") or ""
    st, choice, raw = chat(doc, base, key, doc.model,
                           [{"role": "user", "content": "Say OK."}],
                           max_tokens=16,
                           chat_template_kwargs={"bogus_kwarg_zzq": True,
                                                 "reasoning_effort": "high"})
    doc.evidence["kwarg_probe_status"] = st

    if st is None:
        doc.skip(["07"], "kwarg acceptance probe", "request failed",
                 code="KWARG_PROBE_FAILED",
                 asserts=[A("kwarg probe returned a status", st, held=False)])
        return

    if st == 200:
        if not tpl:
            doc.skip(["07"], "kwarg deadness (reasoning_effort and an invented name)",
                     "the server accepted chat_template_kwargs including an "
                     "invented name without error, and by trap 07's own rule "
                     "acceptance proves nothing about effect. No chat template "
                     "is readable on this stack (llama.cpp /props is the only "
                     "source this tool has), so whether ANY kwarg is actually "
                     "read could not be determined. Fetch the checkpoint's "
                     "chat_template.jinja and run "
                     "checks/preflight_template.py --template-file to settle it.",
                     code="KWARG_ACCEPTED_TEMPLATE_UNREADABLE",
                     asserts=[A("server accepted an invented chat_template_kwarg",
                                {"status": st}),
                              A("a chat template is readable, so acceptance can "
                                "be turned into a verdict", "no template source "
                                "on this stack", held=False)])
            return
        reads_effort = "reasoning_effort" in tpl
        accepted = ("server accepted chat_template_kwargs including an invented "
                    "name without error: acceptance proves nothing about effect")
        detail = (accepted + "; this template never mentions reasoning_effort "
                  "at all, so that knob is dead here")
        if reads_effort:
            # A substring hit means the template MENTIONS the name. It does not
            # mean the mention changes the rendered prompt: the name can sit in
            # a comment, in a branch never taken, or in a `set` that is never
            # used afterwards. This tool's own fixture template is exactly that
            # last shape. Trap 07's failure mode is a knob with no effect, and
            # "the name appears somewhere in the file" does not rule it out.
            doc.inconclusive(["07"], "reasoning_effort deadness",
                             accepted + "; this template MENTIONS "
                             "reasoning_effort, so the knob is REFERENCED"
                             ". A reference is not a read. The name appearing "
                             "in the template text is consistent with a live "
                             "knob, with a mention inside a comment, with a "
                             "branch that never runs, and with a variable that "
                             "is set and then never used. To settle it, render "
                             "the prompt twice through "
                             "checks/preflight_template.py --template-file with "
                             "the value changed and nothing else, and confirm "
                             "the two renders DIFFER. If they are identical the "
                             "knob is dead regardless of what the file mentions.",
                             code="KWARG_REFERENCED_BY_TEMPLATE",
                             asserts=[A("server accepted an invented "
                                        "chat_template_kwarg", {"status": st}),
                                      A("the served chat template mentions "
                                        "reasoning_effort",
                                        {"template_chars": len(tpl),
                                         "found": True}),
                                      A("changing reasoning_effort changes the "
                                        "rendered prompt",
                                        "this tool does not diff two renders; "
                                        "it greps the template text",
                                        held=False)])
        else:
            doc.problem(["07"], detail,
                        "before trusting any kwarg, grep the template for it; "
                        "diff accepted-vs-read in both directions",
                        code="KWARG_ACCEPTED_BUT_DEAD",
                        asserts=[A("server accepted an invented chat_template_kwarg",
                                   {"status": st}),
                                 A("the served chat template contains "
                                   "reasoning_effort",
                                   {"template_chars": len(tpl), "found": False},
                                   held=False)])
        return

    # Non-200. Before crediting the server for rejecting unknown kwargs, prove
    # the rejection is ABOUT the kwargs.
    cst, _cchoice, _craw = chat(doc, base, key, doc.model,
                                [{"role": "user", "content": "Say OK."}],
                                max_tokens=16)
    doc.evidence["kwarg_control_status"] = cst
    if cst != 200:
        doc.skip(["07"], "kwarg deadness (reasoning_effort and an invented name)",
                 f"the kwarg probe failed with http {st}, but so did an "
                 f"identical control request carrying no chat_template_kwargs "
                 f"(http {cst}). The rejection is not attributable to the "
                 f"kwargs, so it says nothing about how this lane handles them.",
                 code="KWARG_REJECTION_UNATTRIBUTABLE",
                 asserts=[A("a control request with no kwargs succeeds",
                            {"kwarg_probe": st, "control": cst}, held=False)])
        return

    bst, _b, _braw = chat(doc, base, key, doc.model,
                          [{"role": "user", "content": "Say OK."}],
                          max_tokens=16,
                          chat_template_kwargs={"bogus_kwarg_zzq": True})
    doc.evidence["kwarg_bogus_only_status"] = bst
    if bst != 200:
        doc.ok(["07"], f"server rejects an invented chat_template_kwarg on its own "
               f"(http {bst}) while an identical request without it succeeds "
               f"(http {cst}): dead knobs are loud here, which is the safe "
               f"direction of trap 07",
               code="KWARG_UNKNOWN_REJECTED",
               asserts=[A("control request with no kwargs succeeds", cst),
                        A("request with only the invented kwarg is rejected", bst)])
    else:
        doc.inconclusive(["07"], "kwarg deadness (reasoning_effort and an "
                         "invented name)",
                         f"the combined probe was rejected (http {st}) but the "
                         f"invented name ALONE was accepted (http {bst}), so the "
                         f"rejection came from reasoning_effort, not from unknown-"
                         f"kwarg strictness. This lane still accepts invented "
                         f"names silently, and whether reasoning_effort is read "
                         f"or merely validated cannot be told from a rejection. "
                         f"Read the template to settle it.",
                         code="KWARG_REJECTION_FROM_KNOWN_NAME",
                         asserts=[A("control request with no kwargs succeeds", cst),
                                  A("request with only the invented kwarg is "
                                    "rejected", bst, held=False)])


def check_tools(doc, base, key):
    """Traps 19 (structured vs prose), 26 (tool markup swallowed by reasoning).

    The old probe defined one tool, asked once, and called any absence of
    tool_calls a parser or template failure. Six states produce that same
    absence: the model elected not to call, the model cannot call, the template
    omits the tools block, the parser failed, the serve flags are missing, or
    the schema was rejected or transformed. This version separates
    MODEL_DID_NOT_CALL from TOOL_MARKUP_NOT_PARSED by forcing a call wherever
    tool_choice is supported, and downgrades its own confidence in writing
    where it cannot.
    """
    forced_choice_spec = {"type": "function", "function": {"name": "get_time"}}
    f_st, f_choice, f_raw = chat(doc, base, key, doc.model,
                                 [{"role": "user", "content":
                                   "What time is it in Tokyo?"}],
                                 max_tokens=256, tools=TOOLS,
                                 tool_choice=forced_choice_spec)
    forced_supported = (f_st == 200 and f_choice is not None)
    f_calls, f_text = [], ""
    if forced_supported:
        fc, frc, frr, f_calls, _ = msg_fields(f_choice)
        f_text = f"{fc}\n{frc}\n{frr}"
    doc.evidence["tool_choice_forced_status"] = f_st

    n_st, n_choice, n_raw = chat(doc, base, key, doc.model,
                                 [{"role": "user", "content":
                                   "What time is it in Tokyo? Use the tool."}],
                                 max_tokens=512, tools=TOOLS,
                                 chat_template_kwargs={"enable_thinking": True})
    doc.evidence["tool_natural_status"] = n_st
    if n_st != 200 or n_choice is None:
        if not forced_supported:
            doc.skip(["19", "26"], "tool-calling probe",
                     f"both the forced-call probe (http {f_st}) and the natural "
                     f"probe (http {n_st}) failed; if your server needs parser "
                     f"flags for tools, that absence is itself trap 19",
                     code="TOOL_PROBES_FAILED",
                     asserts=[A("at least one tools request returns 200",
                                {"forced": f_st, "natural": n_st}, held=False)])
            return
        n_calls, n_text = [], ""
    else:
        nc, nrc, nrr, n_calls, _ = msg_fields(n_choice)
        n_text = f"{nc}\n{nrc}\n{nrr}"

    # KNOWN LIMITATION, recorded rather than papered over. This detects one
    # hardcoded literal. It reached the right verdict on every lane tested so
    # far, and on at least one of them it did so by coincidence: the dialect
    # happened to use this tag. A checkpoint whose markup is a different tag
    # (a bare <function=...>, a [TOOL_CALL] form, or JSON with no wrapper)
    # leaves markup False, and the surrounding logic then reports
    # MODEL_DID_NOT_CALL rather than TOOL_MARKUP_NOT_PARSED. That is a
    # false-INCONCLUSIVE, which is safe, but the mirror case is not: a
    # checkpoint that emits this literal inside ordinary prose would set
    # markup True with no call, which is a latent false PROBLEM.
    #
    # Not fixed here, deliberately. A general detector needs the dialect, and
    # the registry's own trap 84 shows the dialect is a per-checkpoint property
    # that has to be read out of the template rather than guessed. Guessing
    # more tags would widen the false-PROBLEM surface, not narrow it.
    TOOL_MARKUP_LITERALS = ("<tool_call>",)
    markup = any(lit in f_text or lit in n_text for lit in TOOL_MARKUP_LITERALS)
    doc.evidence["tool_calls_seen"] = {"forced": len(f_calls),
                                       "natural": len(n_calls)}

    if f_calls or n_calls:
        who = "forced (tool_choice)" if f_calls else "natural prompt"
        got = (f_calls or n_calls)[0].get("function", {}).get("name")
        doc.ok(["19"], f"one tool defined, structured tool_calls returned on the "
               f"{who} probe (name={got})",
               code="TOOL_CALLS_RETURNED",
               asserts=[A("a tools request returns a structured tool_calls array",
                          {"forced": len(f_calls), "natural": len(n_calls),
                           "name": got})])
        if markup:
            # The assertion here used to read "no raw <tool_call> markup" and
            # record markup_seen=True beside it, held=True. The log said the
            # opposite of the claim and still counted as CLEAN.
            doc.problem(["26"], "structured tool_calls came back, but raw "
                        "<tool_call> markup ALSO appears in the content or "
                        "reasoning text: part of the tool traffic on this lane "
                        "is escaping the parser, so a multi-call turn can be "
                        "half parsed and half left as prose",
                        "on vLLM run a build past PR #35687; on llama.cpp use a "
                        "template that closes think before tool_call. Until "
                        "then, scan content and reasoning for leftover markup "
                        "before scoring any tool-using run",
                        code="TOOL_MARKUP_PARTIALLY_PARSED",
                        asserts=[A("no raw <tool_call> markup in content or "
                                   "reasoning", {"markup_seen": True},
                                   held=False)])
        else:
            doc.ok(["26"], "tool markup is parsed into tool_calls rather than "
                   "left as text inside the reasoning or content channel",
                   code="TOOL_MARKUP_PARSED",
                   asserts=[A("no raw <tool_call> markup in content or reasoning",
                              {"markup_seen": False})])
        if forced_supported and f_calls and not n_calls:
            doc.ok(["19"], "the model returns no call when merely asked, but "
                   "calls correctly when forced with tool_choice: this lane's "
                   "tool plumbing works and the empty natural response is a "
                   "model choice, NOT a parser or template fault",
                   code="MODEL_ELECTS_NOT_TO_CALL",
                   asserts=[A("forced probe calls while natural probe does not",
                              {"forced": len(f_calls), "natural": len(n_calls)})])
        return

    if markup:
        doc.problem(["26"], "tool markup produced but not parsed into tool_calls "
                    "(found inside the reasoning/content text): the parser is "
                    "eating your tool calls",
                    "on vLLM run a build past PR #35687; on llama.cpp use a "
                    "template that closes think before tool_call",
                    code="TOOL_MARKUP_NOT_PARSED",
                    asserts=[A("raw <tool_call> markup appears in text while "
                               "tool_calls is empty", {"markup": True,
                                                       "tool_calls": 0})])
        return

    if forced_supported:
        doc.problem(["19"], "no structured tool_calls even when the call was "
                    "FORCED with tool_choice, and no raw tool markup appeared "
                    "in the text either: this lane cannot emit a tool call at "
                    "all. It is not the model electing to answer in prose",
                    "check serve flags: --jinja and the model's native template "
                    "on llama.cpp, the model-specific tool parser on vLLM; then "
                    "confirm the template actually renders the tools block "
                    "(checks/preflight_template.py)",
                    code="TOOL_CALLING_UNAVAILABLE",
                    asserts=[A("server accepted tool_choice", {"status": f_st}),
                             A("a FORCED tool call returns tool_calls",
                               {"tool_calls": 0}, held=False),
                             A("raw tool markup appears anywhere in the text",
                               {"markup": False}, held=False)])
        return

    # tool_choice not supported: the ambiguity cannot be removed here, so say so
    doc.inconclusive(["19", "26"], "tool-calling capability",
                     f"no structured tool_calls and no raw tool markup with one "
                     f"tool defined, and this server did not accept a forced "
                     f"tool_choice (http {f_st}), so the deterministic control "
                     f"is unavailable. CONFIDENCE: LOW. At least six states "
                     f"produce this result and none were separated: (1) the "
                     f"model elected to answer in prose, (2) the model cannot "
                     f"call tools, (3) the chat template omits the tools block, "
                     f"(4) the server's tool parser is off or mismatched, "
                     f"(5) serve flags for tool parsing are missing, (6) the "
                     f"schema was rejected or silently transformed. Do NOT read "
                     f"this as a template or parser fault. To settle it: render "
                     f"the prompt with the tools attached and confirm the tools "
                     f"block appears (checks/preflight_template.py), then check "
                     f"your server's tool-parser flag.",
                     code="MODEL_DID_NOT_CALL",
                     asserts=[A("server accepts tool_choice, giving a "
                                "deterministic control", {"status": f_st},
                                held=False),
                              A("natural probe returns tool_calls",
                                {"tool_calls": 0}, held=False),
                              A("raw tool markup appears in the text",
                                {"markup": False}, held=False)])


def check_request_validation(doc, base, key):
    """Trap 77: is the request surface validated at all?

    The entry names this probe as its own fix, in its own words: "before you
    trust any new server with an arm of an experiment, send one deliberately
    misspelled parameter and see whether you get a 400. If you get a 200, the
    request surface is unvalidated, your own typos are silent too, and every
    parameter you send is a hypothesis rather than a setting." So this check
    is reading the entry, not inventing a test for it.

    Why it earns a place beside the behavioural toggle checks. Those ask "did
    thinking actually stop", which is the right question and an expensive one:
    it needs a reasoning observable, and on a lane that produces none the
    toggle map is uncharacterised and every arm skips. This asks the cheap
    structural question underneath it, which needs no observable at all: does
    a 200 on this lane carry ANY information about whether the server read
    what you sent? On a lane that answers no, every parameter in every other
    check is a hypothesis, and that is worth knowing before the expensive
    probes run rather than after.

    The CLEAN is paired, and it has to be. "The probe request returned 400" is
    satisfied by a lane that returns 400 for everything: a wrong model name,
    an expired key, a server still loading. That is the false-CLEAN shape this
    tool has produced four times. So the baseline goes first, and CLEAN
    requires an identical request WITHOUT the invented field to have returned
    200. The difference between the two is then attributable to the field.

    What the CLEAN does NOT rule out, stated here because it is the tempting
    over-read: a server that rejects an unknown field can still accept a
    known-but-unimplemented one and ignore it. Rejecting typos is a floor, not
    a guarantee that any particular parameter took effect. The behavioural
    question stays with traps 03 and 29, and the entry's own advice stands
    either way: assert on the response, never on the status code.
    """
    # A name no server implements and no server could plausibly add. Sent at
    # the top level, which is where trap 77 measured it; the entry records
    # that placement inside `options` behaved identically.
    probe_field = "__minefield_unvalidated_field_probe__"
    msgs = [{"role": "user", "content": "hi"}]

    base_st, _, base_txt = chat(doc, base, key, doc.model, msgs, max_tokens=16)
    if base_st != 200:
        doc.inconclusive(
            ["77"], "request-field validation",
            f"the baseline request (nothing invented, nothing unusual) did "
            f"not return 200 (http {base_st}), so a rejection of the probe "
            f"below would say nothing about field validation: a lane that "
            f"rejects everything rejects the probe too. Fix the lane, or the "
            f"model name or key, and re-run.",
            code="VALIDATION_NO_BASELINE",
            asserts=[A("a plain request succeeds",
                       {"status": base_st, "body": str(base_txt)[:160]},
                       held=False)])
        return

    probe_st, _, probe_txt = chat(doc, base, key, doc.model, msgs,
                                  max_tokens=16, **{probe_field: "minefield"})
    doc.evidence["unknown_field_probe_status"] = probe_st

    if probe_st != 200:
        doc.ok(["77"],
               f"the request surface is validated: an invented top-level "
               f"field was rejected (http {probe_st}) while the identical "
               f"request without it returned 200. A misspelled parameter on "
               f"this lane is loud rather than silent",
               code="VALIDATION_REJECTS_UNKNOWN_FIELD",
               asserts=[A("the baseline request succeeds",
                          {"status": base_st}),
                        A("the same request with an invented field is "
                          "rejected",
                          {"field": probe_field, "status": probe_st})])
        return

    doc.problem(
        ["77"],
        f"the request surface is unvalidated: an invented top-level field "
        f"({probe_field}) was accepted with http 200, exactly as the baseline "
        f"without it was. Nothing you send to this lane is confirmed by its "
        f"status code",
        "Treat every request parameter here as a hypothesis until you have "
        "checked the response. Two consequences, both of them cheap to get "
        "wrong: a thinking-off arm that sends a field this server does not "
        "implement is measured on whatever the lane's default is, which on a "
        "thinking-by-default lane means the entire arm is a number about the "
        "wrong configuration; and your own typos are silent, so a parameter "
        "you misspelled reads as a parameter that had no effect. Assert on "
        "the response per request, not per configuration: an arm you believe "
        "is thinking-off must show an absent or empty reasoning field on "
        "every request in it.",
        code="UNKNOWN_FIELD_ACCEPTED",
        asserts=[A("the baseline request succeeds", {"status": base_st}),
                 A("an invented field is rejected",
                   {"field": probe_field, "status": probe_st,
                    "body": str(probe_txt)[:160]}, held=False)])


def check_tool_choice_gate(doc, base, key):
    """Trap 78: tool_choice accepted and ignored, which fails OPEN.

    This is the first check in this tool for anything above trap 55, and it was
    chosen because it is the one with a real consequence: `tool_choice: "none"`
    is the standard way an agent framework says "answer in prose this turn, do
    not call anything". A server that accepts it and calls anyway does not
    produce an outage to investigate; it produces an agent that occasionally
    takes an action on a turn its author believed was read-only.

    The CLEAN here is worth stating carefully, because without a control it
    would be vacuous. "No tool call came back when I sent none" is satisfied by
    a model that simply did not want to call, which is the empty-set shape
    CONTRIBUTING names. So this runs a positive control FIRST: the same
    tool-inviting prompt with no tool_choice at all. Only if that control
    actually produces a call does the suppression in the none-arm mean
    anything, and only then can this emit CLEAN.
    """
    ctrl_st, ctrl_choice, _ = chat(
        doc, base, key, doc.model,
        [{"role": "user", "content": "What time is it in Tokyo? Use the tool."}],
        max_tokens=256, tools=TOOLS)
    if ctrl_st != 200 or ctrl_choice is None:
        doc.inconclusive(["78"], "tool_choice gate",
                         f"the control request (tools attached, no tool_choice) "
                         f"did not return a usable completion (http {ctrl_st}), "
                         f"so there is nothing to gate against.",
                         code="TOOL_CHOICE_NO_CONTROL",
                         asserts=[A("control returns a completion",
                                    {"status": ctrl_st}, held=False)])
        return
    _, _, _, ctrl_calls, _ = msg_fields(ctrl_choice)

    none_st, none_choice, _ = chat(
        doc, base, key, doc.model,
        [{"role": "user", "content": "What time is it in Tokyo? Use the tool."}],
        max_tokens=256, tools=TOOLS, tool_choice="none")
    doc.evidence["tool_choice_none_status"] = none_st

    if none_st != 200 or none_choice is None:
        # A server that REJECTS tool_choice:none is not this trap. It is loud,
        # which is the opposite failure and a safe one.
        doc.ok(["78"], f"tool_choice none is rejected outright (http {none_st}), "
                       f"so it cannot be silently ignored on this lane",
               code="TOOL_CHOICE_REJECTED",
               asserts=[A("tool_choice none is not silently accepted",
                          {"status": none_st})])
        return
    _, _, _, none_calls, _ = msg_fields(none_choice)

    if not ctrl_calls:
        doc.inconclusive(["78"], "tool_choice gate",
                         "the control request did not produce a tool call, so "
                         "an absence of calls under tool_choice none proves "
                         "nothing: the model may simply not have called either "
                         "way. Re-run with a prompt this model reliably calls "
                         "on, or force one with a named tool_choice first.",
                         code="TOOL_CHOICE_NO_CONTROL",
                         asserts=[A("control produces a tool call",
                                    {"tool_calls": len(ctrl_calls)}, held=False)])
        return

    if none_calls:
        doc.problem(
            ["78"],
            "tool_choice none was accepted and ignored: a control with tools "
            "and no tool_choice called a tool, and the identical request with "
            "tool_choice none called one too",
            "Do not rely on tool_choice to gate a turn on this lane. The only "
            "control that works everywhere is to omit the tools payload on "
            "turns where a call must not happen. This fails OPEN, so an agent "
            "loop with a side-effecting tool can act on a turn you believed "
            "was read-only.",
            code="TOOL_CHOICE_IGNORED",
            asserts=[A("control produces a tool call",
                       {"tool_calls": len(ctrl_calls)}),
                     A("tool_choice none suppresses the call",
                       {"tool_calls": len(none_calls)}, held=False)])
        return

    doc.ok(["78"],
           "tool_choice none binds: a control with tools and no tool_choice "
           "called a tool, and the identical request with tool_choice none did "
           "not, so the suppression is attributable to the parameter",
           code="TOOL_CHOICE_NONE_BINDS",
           asserts=[A("control produces a tool call",
                      {"tool_calls": len(ctrl_calls)}),
                    A("tool_choice none suppresses it",
                      {"tool_calls": len(none_calls)})])


def check_ceiling(doc, base, key):
    """Traps 12/16/22: empty content at cap, degeneration vs truncation."""
    st, choice, _ = chat(doc, base, key, doc.model,
                         [{"role": "user", "content":
                           "Write a python function that validates RFC3339 "
                           "timestamps without external libraries, with tests."}],
                         max_tokens=512,
                         chat_template_kwargs={"enable_thinking": True})
    if st != 200 or choice is None:
        doc.skip(["12", "16", "22"], "ceiling probe", f"request failed (http {st})",
                 code="CEILING_PROBE_FAILED",
                 asserts=[A("ceiling probe returns 200", st, held=False)])
        return
    # Trap 22 is a cross-size, cross-budget comparison: the conversion floor is
    # a DISTRIBUTION, and this tool sends one request at one budget to one
    # model. It is never settled here, in either direction, so say so once and
    # never tag a 22 verdict onto the single-probe finding below.
    doc.skip(["22"], "per-size budget floor",
             "trap 22 is a claim about where THIS model size converts reasoning "
             "into content, and a floor is a distribution, not a threshold: the "
             "registry's own production replication has a 27B convert 0/3 at "
             "8192 and only 2/3 at 16384, so it still fails 1 in 3 at a budget "
             "where it also succeeds. This tool sends ONE request at ONE budget "
             "(max_tokens=512) to ONE model, which cannot characterise a "
             "distribution and cannot compare sizes. Whatever the probe below "
             "reports, it is not a trap-22 result. Run the multi-budget, "
             "multi-sample procedure in the trap 22 entry against every size "
             "you serve.",
             code="BUDGET_FLOOR_NOT_CHARACTERISED",
             asserts=[A("the ceiling probe sweeps more than one token budget",
                        {"budgets_probed": [512], "samples_per_budget": 1},
                        held=False)])

    c, rc, rr, _t, _ = msg_fields(choice)
    fr = choice.get("finish_reason")
    reason = rc or rr
    has_content = bool(c.strip())
    if fr == "length" and not has_content:
        lines = [l for l in reason.splitlines() if l.strip()]
        uniq = len(set(lines)) / max(1, len(lines))
        z = len(zlib.compress(reason.encode())) / max(1, len(reason))
        degenerate = not (uniq > 0.5 and z > 0.2)
        kind = "possible degeneration loop" if degenerate else "honest truncation"
        doc.problem(["12"],
                    f"hard task at max_tokens=512: HTTP 200, finish=length, "
                    f"EMPTY content, {len(reason)} chars of reasoning "
                    f"({kind}: unique-line {uniq:.2f}, zlib {z:.2f}). If your "
                    f"harness scores this zero, it is measuring your budget",
                    "bucket cap-hits before scoring; find THIS model's "
                    "conversion floor (family advice does not transfer)",
                    code="EMPTY_CONTENT_AT_CAP",
                    asserts=[A("a cap-hitting response carries content",
                               {"finish_reason": fr, "content_chars": len(c)},
                               held=False)])
        if degenerate:
            # An annotation on the finding above, not a second verdict, and
            # deliberately not tagged onto trap 16: trap 16 is about scoring
            # finish_reason, which the PROBLEM above already covers.
            doc.inconclusive(["12"], "reasoning text at the cap looks repetitive",
                             f"the reasoning returned at the cap has "
                             f"unique-line {uniq:.2f} and zlib ratio {z:.2f}, "
                             f"which is the shape of a degeneration loop rather "
                             f"than an answer that ran out of room. This is a "
                             f"two-number heuristic over one sample and it does "
                             f"NOT establish degeneration: a genuinely "
                             f"repetitive task produces the same shape. Re-run "
                             f"at a higher budget and read the trace before "
                             f"concluding either way.",
                             code="CAP_REASONING_LOOKS_DEGENERATE",
                             asserts=[A("repetition was distinguished from a "
                                        "repetitive task by more than a "
                                        "two-number heuristic on one sample",
                                        {"unique_line_ratio": round(uniq, 2),
                                         "zlib_ratio": round(z, 2),
                                         "samples": 1}, held=False)])
    elif has_content and fr == "length":
        # The cap WAS reached and content came back anyway. That is the only
        # observation on this probe that rules the trap-12 failure mode out,
        # because the failure mode is specifically "cap hit, content empty".
        doc.ok(["12"], f"hard task at max_tokens=512: the cap WAS reached "
               f"(finish=length) and content came back anyway ({len(c)} chars), "
               f"so this lane converts reasoning into content at this budget. "
               f"Scoped to this budget and this one sample",
               code="CONTENT_PRESENT_AT_CAP_HIT",
               asserts=[A("the probe reached the token cap",
                          {"finish_reason": fr}),
                        A("a cap-hitting response carries content",
                          {"content_chars": len(c)})])
    elif has_content:
        # Content present, but the cap was never reached, so the empty-at-cap
        # failure mode was never exercised. The old code called this CLEAN.
        # A request that finished early is not a negative for a defect that
        # only appears when the budget runs out.
        doc.inconclusive(["12"], "empty content at the token ceiling",
                         f"the probe returned {len(c)} chars of content with "
                         f"finish_reason={fr!r}, so it never reached the cap at "
                         f"all. Trap 12's failure mode is content going EMPTY "
                         f"when the budget runs out, and a request that "
                         f"finished early does not exercise it. This is not a "
                         f"negative result, it is an untested one, and one "
                         f"sample at one budget could not settle it even if it "
                         f"had hit the cap: the registry's own data has a model "
                         f"fail 1 in 3 at a budget where it also passes. Run "
                         f"the multi-sample budget probe in the trap 12 entry "
                         f"before recording this lane as clean.",
                         code="CEILING_NOT_REACHED",
                         asserts=[A("the probe reached the token cap, so the "
                                    "empty-at-cap failure mode was exercised",
                                    {"finish_reason": fr,
                                     "content_chars": len(c)}, held=False)])
    else:
        # Empty content that did NOT hit the cap. The old code called this
        # clean because it only tested for finish=length. An empty answer is
        # never a clean result, and it is exactly the trap-16 shape: the exit
        # reason says nothing went wrong while nothing was produced.
        doc.inconclusive(["12", "16"], "empty content on the ceiling probe",
                         f"the response carried NO content ({len(reason)} chars "
                         f"of reasoning) yet finish_reason={fr!r}, not 'length'. "
                         f"This is not a cap hit and it is not a clean answer. "
                         f"Candidate causes this probe cannot separate: the "
                         f"answer landed entirely in the reasoning channel "
                         f"(trap 23), a stop string fired early, the parser "
                         f"consumed the answer, or the model genuinely returned "
                         f"nothing. A harness scoring this run would record a "
                         f"zero for a request the server called successful.",
                         code="EMPTY_CONTENT_NOT_AT_CAP",
                         asserts=[A("the ceiling probe returns non-empty content",
                                    {"finish_reason": fr, "content_chars": 0,
                                     "reasoning_chars": len(reason)}, held=False)])


# ------------------------------------------------------- huggingface configs

def hf_resolve_revision(repo, revision):
    """Resolve a revision (branch, tag, or sha) to an immutable commit sha.

    Without this the doctor always read `resolve/main`, so an operator serving
    a pinned older revision was compared against today's mutable main and told
    they had drift that does not exist on the checkpoint they are running.
    Returns (sha_or_None, note).
    """
    st, txt = get(f"{HF_BASE}/api/models/{repo}/revision/{revision}")
    if st == 200:
        try:
            sha = json.loads(txt).get("sha")
            if sha:
                return sha, f"resolved {revision!r} to commit {sha}"
        except Exception:
            pass
    return None, (f"could not resolve {revision!r} to a commit sha "
                  f"(hub API http {st}); files below were read at the mutable "
                  f"ref {revision!r}, which can change under you")


def check_configs(doc, hf_repo, hf_revision="main"):
    """Traps 21 (generation_config missing), 17 (defaults vs card), 10 (quant)."""
    props = doc.evidence.get("props")
    if props:
        p = (props.get("default_generation_settings") or {}).get("params", {})
        eff = {k: round(v, 3) if isinstance(v, float) else v
               for k, v in p.items()
               if k in ("temperature", "top_k", "top_p", "min_p", "presence_penalty")}
        doc.evidence["server_defaults"] = eff
    else:
        eff = None
    if not hf_repo:
        doc.skip(["21", "17", "10"], "generation_config / card-sampling / quant "
                 "scheme checks",
                 "pass --hf-repo org/name to compare against the checkpoint's "
                 "shipped configs (and --hf-revision if you serve a pinned "
                 "revision rather than main)",
                 code="NO_HF_REPO",
                 asserts=[A("--hf-repo supplied", None, held=False)])
        return

    sha, note = hf_resolve_revision(hf_repo, hf_revision)
    ref = sha or hf_revision
    pinned = bool(sha)
    doc.evidence["hf"] = {"repo": hf_repo, "requested_revision": hf_revision,
                          "resolved_commit": sha, "read_at_ref": ref,
                          "note": note}
    scope = (f"{hf_repo} @ {hf_revision}"
             + (f" (commit {sha[:12]})" if sha else " (UNRESOLVED ref)"))
    rev_assert = A("the requested revision resolved to an immutable commit",
                   {"requested": hf_revision, "resolved": sha}, held=pinned)
    if not pinned:
        doc.inconclusive(["21", "17", "10"], f"revision pinning for {hf_repo}",
                         note + ". Every config comparison below is against a "
                         "ref that can move, so a reported difference may be "
                         "drift in the hub rather than in your lane. Re-run "
                         "with --hf-revision <commit sha> to make the "
                         "comparison reproducible.",
                         code="HF_REVISION_UNRESOLVED",
                         asserts=[rev_assert])

    base_url = f"{HF_BASE}/{hf_repo}/resolve/{ref}"

    st, txt = get(f"{base_url}/generation_config.json")
    if st == 200:
        try:
            gc = json.loads(txt)
            doc.ok(["21"], f"generation_config.json exists on {scope} "
                   f"(keys: {sorted(gc.keys())[:6]})",
                   code="GENERATION_CONFIG_PRESENT",
                   asserts=[rev_assert,
                            A("generation_config.json is readable at the "
                              "compared revision", {"ref": ref, "status": st})])
            if eff:
                shared = [k for k in eff if k in gc]
                diffs = {k: (eff.get(k), gc.get(k)) for k in shared
                         if not _close(eff.get(k), gc.get(k))}
                if diffs:
                    doc.problem(["17"], f"server defaults differ from the "
                                f"generation_config shipped at {scope}: {diffs} "
                                f"(server, checkpoint)",
                                "set sampling explicitly per request; never "
                                "describe a run as 'model defaults' across stacks",
                                code="SAMPLING_DEFAULTS_DIFFER",
                                asserts=[rev_assert,
                                         A("server defaults equal the checkpoint's "
                                           "generation_config on every shared key",
                                           {"compared": shared, "diffs": diffs},
                                           held=False)])
                elif shared:
                    doc.ok(["17"], f"server defaults match the generation_config "
                           f"shipped at {scope} on every key both sides declare "
                           f"({', '.join(shared)}); keys only one side declares "
                           f"were not compared",
                           code="SAMPLING_DEFAULTS_MATCH",
                           asserts=[rev_assert,
                                    A("server defaults equal the checkpoint's "
                                      "generation_config on every shared key",
                                      {"compared": shared,
                                       "server_only": sorted(set(eff) - set(gc)),
                                       "checkpoint_only": sorted(
                                           k for k in gc if k in
                                           ("temperature", "top_k", "top_p",
                                            "min_p", "presence_penalty")
                                           and k not in eff)})])
                else:
                    doc.skip(["17"], "server defaults vs shipped generation_config",
                             f"the server publishes {sorted(eff)} and the "
                             f"checkpoint's generation_config declares "
                             f"{sorted(gc)}; the two sets do not overlap, so "
                             f"there is nothing to compare and no basis for "
                             f"calling the sampling aligned",
                             code="SAMPLING_NO_SHARED_KEYS",
                             asserts=[rev_assert,
                                      A("server and checkpoint declare at least "
                                        "one common sampling key",
                                        {"server": sorted(eff),
                                         "checkpoint": sorted(gc)}, held=False)])
            else:
                doc.skip(["17"], "server defaults vs shipped generation_config",
                         "this stack publishes no effective sampling defaults "
                         "(llama.cpp /props is the only source this tool has), "
                         "so the checkpoint's generation_config cannot be "
                         "compared against what your server will actually use",
                         code="SERVER_DEFAULTS_UNREADABLE",
                         asserts=[rev_assert,
                                  A("the server publishes its effective sampling "
                                    "defaults", None, held=False)])
        except Exception:
            doc.skip(["21", "17"], "generation_config parse", "unparseable JSON",
                     code="GENERATION_CONFIG_UNPARSEABLE",
                     asserts=[rev_assert,
                              A("generation_config.json parses as JSON", txt[:120],
                                held=False)])
    elif st == 404:
        detail = (f"{scope} ships NO generation_config.json: there is no such "
                  f"thing as 'model defaults' on this checkpoint")
        if eff:
            detail += f"; you are silently running your server's built-ins: {eff}"
        doc.problem(["21"], detail,
                    "take sampling from the card's prose, per mode, and set it "
                    "explicitly on every request",
                    code="NO_GENERATION_CONFIG",
                    asserts=[rev_assert,
                             A("the checkpoint ships generation_config.json",
                               {"ref": ref, "status": 404}, held=False)])
        doc.skip(["17"], "server defaults vs shipped generation_config",
                 "there is no shipped generation_config at this revision to "
                 "compare against",
                 code="SAMPLING_NO_BASELINE",
                 asserts=[rev_assert])
    else:
        doc.skip(["21", "17"], "generation_config fetch",
                 f"http {st} from the hub at {scope}",
                 code="GENERATION_CONFIG_FETCH_FAILED",
                 asserts=[rev_assert,
                          A("generation_config.json is readable at the compared "
                            "revision", {"ref": ref, "status": st}, held=False)])

    st, txt = get(f"{base_url}/config.json")
    if st == 200:
        try:
            cfg = json.loads(txt)
            qc = cfg.get("quantization_config")
            if qc:
                # A manifest proves the checkpoint is LABELLED. Trap 10's
                # failure mode is the engine taking a different kernel path
                # from the one the label implies, and no file on the hub can
                # rule that out. This used to be CLEAN while its own prose
                # said "the label is not the kernel path".
                doc.inconclusive(["10"], f"quantisation scheme at {scope}",
                                 f"config.json declares quantization_config: "
                                 f"method={qc.get('quant_method')}, ignore list "
                                 f"{'present' if qc.get('ignore') else 'ABSENT'}. "
                                 f"That establishes what the checkpoint is "
                                 f"LABELLED, and nothing more. Trap 10 is about "
                                 f"the engine taking a different kernel path "
                                 f"from the one the label implies, and this "
                                 f"check reads files on the hub, never your "
                                 f"running engine, so it cannot tell a fast "
                                 f"format-matched path from a slow fallback "
                                 f"wearing the same name. Settle it with a "
                                 f"RUNTIME tell: grep the engine's "
                                 f"backend-selection log for the kernel it "
                                 f"actually chose, or measure decode throughput "
                                 f"against an f16 baseline of the same model, or "
                                 f"compare GPU utilisation against power draw. "
                                 f"Until one of those runs, the kernel path is "
                                 f"UNKNOWN.",
                                 code="QUANT_IN_CONFIG_JSON",
                                 asserts=[rev_assert,
                                          A("config.json declares "
                                            "quantization_config",
                                            {"quant_method": qc.get("quant_method"),
                                             "has_ignore": bool(qc.get("ignore"))}),
                                          A("a runtime tell confirms the engine "
                                            "took the kernel path the label "
                                            "implies",
                                            "no runtime tell is read by this "
                                            "check; it reads hub files only",
                                            held=False)])
            else:
                # ModelOpt and several other producers keep the manifest in a
                # sibling file. Reporting "unquantized checkpoint" as a CLEAN
                # result for a 4-bit checkpoint is exactly the false negative
                # trap 10 exists to prevent, so look before concluding.
                st2, txt2 = get(f"{base_url}/hf_quant_config.json")
                if st2 == 200:
                    try:
                        hq = json.loads(txt2)
                        qc2 = hq.get("quantization") or hq
                        doc.inconclusive(
                            ["10"], f"quantisation scheme at {scope} "
                            f"(manifest outside config.json)",
                            f"quantisation is declared in "
                            f"hf_quant_config.json, NOT in config.json "
                            f"(quant_algo={qc2.get('quant_algo')}, "
                            f"producer={qc2.get('producer') or hq.get('producer')}). "
                            f"Locating that manifest is a real result: tooling "
                            f"that only reads config.json will call this "
                            f"checkpoint unquantized. It is still only the "
                            f"LABEL. Trap 10 is about the engine taking a "
                            f"different kernel path from the one the label "
                            f"implies, and this check reads hub files, never "
                            f"your running engine. A compressed-tensors "
                            f"NVFP4 or MXFP4 checkpoint routing to a slow "
                            f"marlin fallback carries exactly this manifest. "
                            f"Settle it with a RUNTIME tell: grep the engine's "
                            f"backend-selection log for the kernel it actually "
                            f"chose, or measure decode throughput against an "
                            f"f16 baseline of the same model, or compare GPU "
                            f"utilisation against power draw. Until one of "
                            f"those runs, the kernel path is UNKNOWN.",
                            code="QUANT_IN_HF_QUANT_CONFIG",
                            asserts=[rev_assert,
                                     A("the quantisation manifest was located",
                                       {"config.json": False,
                                        "hf_quant_config.json": True}),
                                     A("hf_quant_config.json declares the scheme",
                                       {"quant_algo": qc2.get("quant_algo")}),
                                     A("a runtime tell confirms the engine took "
                                       "the kernel path the label implies",
                                       "no runtime tell is read by this check; "
                                       "it reads hub files only", held=False)])
                    except Exception:
                        doc.skip(["10"], "hf_quant_config.json parse",
                                 "present but unparseable; quantisation scheme UNKNOWN",
                                 code="QUANT_MANIFEST_UNPARSEABLE",
                                 asserts=[rev_assert,
                                          A("hf_quant_config.json parses as JSON",
                                            txt2[:120], held=False)])
                else:
                    doc.skip(["10"], "quantisation scheme",
                             f"no quantization_config in config.json and no "
                             f"hf_quant_config.json either at {scope}. This may "
                             f"be an unquantized checkpoint, or the manifest may "
                             f"live somewhere this check does not look. UNKNOWN, "
                             f"not clean",
                             code="QUANT_SCHEME_UNKNOWN",
                             asserts=[rev_assert,
                                      A("config.json declares quantization_config",
                                        None, held=False),
                                      A("hf_quant_config.json exists",
                                        {"status": st2}, held=False)])
        except Exception:
            doc.skip(["10"], "config.json parse", "unparseable JSON",
                     code="CONFIG_JSON_UNPARSEABLE",
                     asserts=[rev_assert,
                              A("config.json parses as JSON", txt[:120], held=False)])
    else:
        doc.skip(["10"], "config.json fetch", f"http {st} at {scope}",
                 code="CONFIG_JSON_FETCH_FAILED",
                 asserts=[rev_assert,
                          A("config.json is readable at the compared revision",
                            {"ref": ref, "status": st}, held=False)])


def _close(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-3
    except Exception:
        return a == b

# ------------------------------------------------------------------ coverage

def coverage(doc):
    """What this run actually touched, so a clean run cannot be read as a
    broad bill of health over the registry."""
    implemented = set(TRAP_PATHS)
    prob = doc.trap_ids("PROBLEM")
    clean = doc.trap_ids("OK") - prob
    unsure = (doc.trap_ids("INCONCLUSIVE") | doc.trap_ids("UNKNOWN")) - prob - clean
    executed = prob | clean
    return {
        "registry_total": REGISTRY_TRAP_COUNT,
        "implemented": sorted(implemented),
        "executed": sorted(executed),
        "clean": sorted(clean),
        "problems": sorted(prob),
        "inconclusive": sorted(unsure),
        "not_implemented_count": REGISTRY_TRAP_COUNT - len(implemented),
        "shared_heuristic": TRAPS_SHARED_HEURISTIC,
        "never_clean": TRAPS_NEVER_CLEAN,
        "advisory": sorted(ADVISORY_IDS),
        "need_hf_repo": sorted(TRAPS_NEED_HF_REPO),
        "need_render_path": sorted(TRAPS_NEED_RENDER_PATH),
        "core_total": sorted(CORE_TRAP_IDS),
        "core_implemented": sorted(CORE_TRAP_IDS & implemented),
        "core_executed": sorted(CORE_TRAP_IDS & executed),
        "core_not_implemented": sorted(CORE_TRAP_IDS - implemented),
    }


def coverage_line(cov):
    return (f"implemented {len(cov['implemented'])}/{cov['registry_total']} | "
            f"executed on this stack {len(cov['executed'])} | "
            f"clean {len(cov['clean'])} | problems {len(cov['problems'])} | "
            f"inconclusive {len(cov['inconclusive'])} | "
            f"not implemented {cov['not_implemented_count']}")

# ------------------------------------------------------------------ output

def emit(doc, args):
    def T(ns):
        out = []
        for n in ns:
            if n in TRAP_PATHS:
                out.append(f"[trap {n}]({trap(n)})")
            elif n in ADVISORY_IDS:
                # Not a numbered entry. Say so on the line itself, so nobody
                # goes looking for a trap file or a README row that does not
                # exist, and so an advisory PROBLEM is not mistaken for a
                # registry-backed one.
                out.append(f"{n} (advisory, not in the registry: "
                           f"{ADVISORY_IDS[n]})")
            else:
                out.append(f"[registry draft: {n}]({trap(n)})")
        return " ".join(out)
    print(f"\nminefield-doctor: {args.base_url}")
    print(f"stack={doc.stack} model={doc.model} build={doc.build or 'n/a'} "
          f"requests_made={doc.requests_made}\n")

    print(f"== PROBLEMS ({len(doc.problems)}) ==")
    for f in doc.problems:
        print(f"  ! {f['title']}\n    fix: {f['detail']}\n    see: {T(f['traps'])}")
    if not doc.problems:
        print("  none found by the checks that ran")

    print(f"\n== CHECKED AND CLEAN ({len(doc.clean)}) ==")
    for f in doc.clean:
        print(f"  + {f['title']}\n    see: {T(f['traps'])}")
    if not doc.clean:
        print("  nothing reached a clean verdict on this stack")

    print(f"\n== INCONCLUSIVE ({len(doc.unsure)}) ==")
    print("  (the probe ran, but the result is consistent with several "
          "materially\n   different states; this is NOT a clean result)")
    for f in doc.unsure:
        print(f"  ~ {f['title']}\n    why: {f['detail']}\n    see: {T(f['traps'])}")
    if not doc.unsure:
        print("  none")

    print(f"\n== COULD NOT CHECK ({len(doc.blocked)}) ==")
    for f in doc.blocked:
        print(f"  ? {f['title']}\n    why: {f['detail']}\n    see: {T(f['traps'])}")
    if not doc.blocked:
        print("  every check ran")

    cov = coverage(doc)
    print("\n== COVERAGE ==")
    print(f"  {coverage_line(cov)}")
    print(f"  counted over trap ids, against a registry of "
          f"{cov['registry_total']} numbered entries.")
    print(f"  executed = a trap id that received a CLEAN or PROBLEM verdict on "
          f"this run.")
    print(f"  implemented ids: {', '.join(cov['implemented'])}")
    if cov["problems"]:
        print(f"  problems on: {', '.join(cov['problems'])}")
    if cov["inconclusive"]:
        print(f"  inconclusive or unchecked: {', '.join(cov['inconclusive'])}")
    print(f"  Core tier ({len(cov['core_total'])} entries, see CORE.md): "
          f"implemented here {', '.join(cov['core_implemented'])}; "
          f"executed on this run "
          f"{', '.join(cov['core_executed']) or 'none'}.")
    print(f"    Core entries with NO check in this tool, and therefore yours "
          f"to run by hand: {', '.join(cov['core_not_implemented'])}. "
          f"Findings above are printed Core first within each bucket.")
    print("  caveats on the implemented count, so it is not read as depth:")
    for n, why in sorted(cov["shared_heuristic"].items()):
        print(f"    - {n}: {why}")
    for n, why in sorted(cov["never_clean"].items()):
        print(f"    - {n}: NEVER REACHES CLEAN. {why}")
    print(f"    - {', '.join(cov['need_hf_repo'])}: need --hf-repo; without it "
          f"they cannot run at all")
    print(f"    - {', '.join(cov['need_render_path'])}: need a render path; on a "
          f"stack with none they cannot run at all")
    print(f"  advisory checks, counted nowhere above because they are NOT "
          f"numbered registry entries: {', '.join(cov['advisory'])}. They can "
          f"report a PROBLEM or a CLEAN of their own, and there is no trap file "
          f"or README row behind any of them.")
    unaccounted = sorted(set(cov["implemented"])
                         - set(cov["executed"]) - set(cov["inconclusive"]))
    if unaccounted:
        print("  implemented but NOT exercised on this run, in either "
              "direction: " + ", ".join(unaccounted))
        print("    a check exists for these and this run gave them no verdict, "
              "clean or otherwise. They are not covered by anything above.")
    print(f"  the remaining {cov['not_implemented_count']} numbered traps have "
          f"no check in this tool. A clean run above is a statement about "
          f"{len(cov['clean'])} trap ids, not about the registry.")

    if args.report:
        print("\n== PASTE-READY REPORT (for an 'I hit a trap' issue) ==\n")
        print("```markdown")
        print("**What were you serving**")
        print(f"- stack: {doc.stack} ({doc.build or 'build unknown'})")
        print(f"- model: {doc.model}")
        print("- endpoint: (host redacted by doctor; add server flags yourself)")
        print(f"- doctor coverage: {coverage_line(cov)}")
        print(f"- doctor findings ({len(doc.problems)} problem(s)):")
        for f in doc.problems:
            print(f"  - {f['title']} (traps {', '.join(f['traps'])})")
        if doc.unsure:
            print(f"- inconclusive ({len(doc.unsure)}):")
            for f in doc.unsure:
                print(f"  - {f['title']} (traps {', '.join(f['traps'])})")
        print("\n**What broke / what you saw**\n<your words here>")
        print("\n**What fixed it**\n<if anything>")
        print("```")


def run(doc, base, root, args):
    """Every check, in order. Split out of main() so the regression suite can
    drive a full run against a fixture server without going through argv."""
    # First, because it is the cheapest and because it qualifies every check
    # after it: on a lane that accepts anything, every parameter the checks
    # below send is a hypothesis rather than a setting.
    check_request_validation(doc, base, args.api_key)
    check_reasoning_fields(doc, base, args.api_key)
    check_streaming(doc, base, args.api_key)
    check_history_assembly(doc, root, args.api_key)
    check_kwarg_deadness(doc, base, root, args.api_key)
    check_multimodal(doc, base, root, args.api_key)
    check_tools(doc, base, args.api_key)
    check_tool_choice_gate(doc, base, args.api_key)
    check_ceiling(doc, base, args.api_key)
    check_configs(doc, args.hf_repo, args.hf_revision)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True,
                    help="OpenAI-compatible base, e.g. http://localhost:8000/v1")
    ap.add_argument("--model", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--hf-repo", default=None,
                    help="org/name of the checkpoint, enables config checks")
    ap.add_argument("--hf-revision", default="main",
                    help="branch, tag or commit sha of the checkpoint you are "
                         "actually serving. Defaults to main, which is MUTABLE: "
                         "if you serve a pinned revision, pass it here or the "
                         "comparison is against a checkpoint you do not run.")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    root = base[:-3].rstrip("/")
    doc = Doc()
    if not detect_stack(doc, base, root, args.api_key):
        print(f"unreachable: {base}/models did not answer", file=sys.stderr)
        sys.exit(1)
    if args.model:
        doc.model = args.model
    run(doc, base, root, args)
    emit(doc, args)
    if args.json:
        cov = coverage(doc)
        with open(args.json, "w") as f:
            json.dump({"stack": doc.stack, "model": doc.model,
                       "requests_made": doc.requests_made,
                       "coverage": cov,
                       "coverage_line": coverage_line(cov),
                       "findings": doc.findings,
                       "problems": [(f["traps"], f["title"], f["detail"])
                                    for f in doc.problems],
                       "clean": [(f["traps"], f["title"]) for f in doc.clean],
                       "inconclusive": [(f["traps"], f["title"], f["detail"])
                                        for f in doc.unsure],
                       "could_not_check": [(f["traps"], f["title"], f["detail"])
                                           for f in doc.blocked],
                       "evidence": doc.evidence}, f, indent=1, default=str)

if __name__ == "__main__":
    main()
