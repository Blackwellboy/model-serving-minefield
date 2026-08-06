#!/usr/bin/env python3
"""Render-path and multimodal coverage, against a Nemotron-shaped mock lane.

This complements test_doctor_verdicts.py. That suite drives declared fixtures
to pin every verdict; this one drives a mock that reproduces one real family's
actual defects, so a pass means the doctor detects THOSE, not merely that its
verdict vocabulary is internally consistent.

Defect A: "no render path on this stack" was reported on every vLLM lane, so
          traps 04, 20 and 25 were never checked there. vLLM exposes
          /v1/chat/completions/render (token ids) and /detokenize.

Defect B: no multimodal coverage at all. The doctor sent no media and then
          reported a full set of clean checks on a multimodal lane.

Defect F: an NVFP4 checkpoint whose manifest lives in hf_quant_config.json was
          reported CLEAN as "unquantized checkpoint".

The mock lane's preservation switch is `truncate_history_thinking: false`,
which is the OPPOSITE polarity to the registry's documented
`preserve_thinking: true`. A doctor that only knows one polarity passes every
other assertion here and still misses the fix, which is why that case is
asserted explicitly.

All against a local mock lane. No real endpoint is contacted. To also print a
before/after against a pre-fix copy of the doctor, set
MINEFIELD_DOCTOR_OLD=/path/to/old/minefield_doctor.py.

    python3 doctor/tests/test_doctor_render_and_multimodal.py
"""
import importlib.util
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mock_vllm_lane import MockLane  # noqa: E402

NEW = HERE.parent / "minefield_doctor.py"
OLD = Path(os.environ["MINEFIELD_DOCTOR_OLD"]) if os.environ.get(
    "MINEFIELD_DOCTOR_OLD") else None

fails = []


def check(label, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        fails.append(label)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_doctor(mod, base):
    """Drive the module the way main() does, without argparse or sys.exit."""
    doc = mod.Doc()
    b = base.rstrip("/")
    root = b[:-3].rstrip("/")
    assert mod.detect_stack(doc, b, root, None), "mock lane unreachable"
    mod.check_reasoning_fields(doc, b, None)
    mod.check_history_assembly(doc, root, None)
    if hasattr(mod, "check_multimodal"):
        mod.check_multimodal(doc, b, root, None)
    return doc


def texts(findings):
    """Every prose field of each finding, whether it is a dict (current shape)
    or a tuple (the pre-hardening shape, for the optional before/after)."""
    out = []
    for f in findings:
        if isinstance(f, dict):
            out.append(" ".join(str(x) for x in (f["title"], f.get("detail") or "")))
        else:
            out.append(" ".join(str(x) for x in f[1:]))
    return out


new = load(NEW, "doc_new")
old = load(OLD, "doc_old") if OLD and OLD.exists() else None

# ------------------------------------------------------------------ defect A
with MockLane("broken") as base:
    buf = io.StringIO()
    with redirect_stdout(buf):
        d_new = run_doctor(new, base)

    blocked_new = " || ".join(texts(d_new.blocked))
    check("A: vLLM lane no longer reports 'no render path'",
          "no render path" not in blocked_new, blocked_new[:120])

    all_new = " || ".join(texts(d_new.problems) + texts(d_new.clean))
    check("A: the render actually came from the server route",
          "/v1/chat/completions/render" in all_new)

    probs = texts(d_new.problems)
    check("A: empty think shells in history are now detected",
          any("empty think" in t for t in probs), " | ".join(probs)[:160])

    gate = d_new.evidence.get("preservation_gate")
    check("A: the working preservation kwarg is found, with its polarity",
          gate is not None and gate[0] == "truncate_history_thinking"
          and gate[1] is False, str(gate))
    check("A: the finding names the kwarg and the field to resend",
          any("truncate_history_thinking" in t and "reasoning" in t for t in probs))

    # every not-clean verdict must carry at least one assertion that failed,
    # and every clean one must carry only assertions that held
    for f in d_new.findings:
        if f["level"] == "OK":
            check(f"A: clean verdict {f['code']} carries held evidence",
                  bool(f["assertions"])
                  and all(a["result"] == "held" for a in f["assertions"]))
        else:
            check(f"A: not-clean verdict {f['code']} names what was unverified",
                  any(a["result"] == "failed" for a in f["assertions"]))

    if old:
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            d_old = run_doctor(old, base)
        blocked_old = " || ".join(texts(d_old.blocked))
        check("A: the OLD code did report 'no render path' on the same lane",
              "no render path" in blocked_old, blocked_old[:100])
        print(f"      before: {len(d_old.problems)} problems, "
              f"{len(d_old.clean)} clean, {len(d_old.blocked)} could-not-check")
        print(f"      after:  {len(d_new.problems)} problems, "
              f"{len(d_new.clean)} clean, {len(d_new.blocked)} could-not-check")

    # -------------------------------------------------------------- defect B
    blocked = texts(d_new.blocked)
    cleans = texts(d_new.clean)

    check("B: multimodal surface is probed, not assumed",
          any("accepts inline image parts" in t for t in cleans))
    check("B: discarded part order is detected",
          any("ORDER IS DISCARDED" in t for t in probs))
    check("B: 5xx on a bad media path is detected",
          any("server fault" in t for t in probs))
    check("B: null prompt_tokens_details is detected",
          any("not attributable" in t for t in probs))
    check("B: audio and video are declared uncovered, not silently clean",
          any("audio and video" in t.lower() for t in blocked))

# a lane that does these things correctly must NOT be reported as broken
with MockLane("clean") as base:
    buf = io.StringIO()
    with redirect_stdout(buf):
        d_ok = run_doctor(new, base)
    probs = texts(d_ok.problems)
    cleans = texts(d_ok.clean)
    check("B: a correct lane is not flagged for part order",
          not any("ORDER IS DISCARDED" in t for t in probs))
    check("B: a correct lane is credited for preserving order",
          any("order is preserved" in t for t in cleans))
    check("B: a correct lane is not flagged for media error class",
          not any("server fault" in t for t in probs))
    check("B: a 4xx media error is credited",
          any("caller error" in t for t in cleans))
    check("B: populated usage details are credited",
          any("attributable from the usage block" in t for t in cleans))
    check("B: audio and video are STILL declared uncovered on a clean lane",
          any("audio and video" in t.lower() for t in texts(d_ok.blocked)))

# ------------------------------------------------------------------ defect F
# the hub is not contacted by this file, so exercise the branch shapes in source
src = NEW.read_text(encoding="utf-8")
check("F: config.json miss now consults hf_quant_config.json",
      "hf_quant_config.json" in src)
check("F: config.json miss no longer reports 'unquantized' as CLEAN",
      'doc.ok(["10"], "no quantization_config' not in src)
check("F: the unknown case is a skip, not a clean",
      'doc.skip(["10"], "quantisation scheme"' in src)

print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)
print("ALL PASS")
