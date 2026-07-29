#!/usr/bin/env python3
"""Trap 44 check: did your offline dequant use the right scale layout?

Two assertions, because either alone passes on a subtly broken model:

  1. PER-ROW cosine in float64 between dequantized and base weights. A FLAT cosine over
     a 1.27B-element lm_head overflows in float32 and can return > 1, which is itself
     the tell that your metric is broken rather than your weights.
  2. Generation probes. The capital-of-France probe PASSES on a wrong-layout dequant.
     The decimal-comparison probe does not. Run both.

Reference points: swizzle=True gave cosine 0.92 and a destroyed model (immediate EOS,
"9.9 vs 9.11" answered "9 and 9"); swizzle=False gave 0.9967 and a coherent one.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 dequant_fidelity.py --base PATH --dequant PATH    (needs torch + safetensors)
  python3 dequant_fidelity.py --base-url URL --model NAME   (stdlib only)
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

PROBES = [
    ("capital", "What is the capital of France? Answer with one word.",
     lambda s: "paris" in s.lower()),
    ("decimal", "Which is larger, 9.9 or 9.11? Answer with just the number.",
     lambda s: "9.9" in s and "9.11" not in s.split("9.9")[0]),
    ("nonempty", "Say the word: ok", lambda s: len(s.strip()) > 0),
]


def evaluate_cosines(per_tensor, threshold):
    """Pure core. `per_tensor` is a list of (name, p01_cosine) for tensors ACTUALLY compared.

    An empty list is NOTHING_INSPECTED, never OK. This is the defect the original
    version of this check shipped with: `worst` started at 1.0 and every tensor could
    be skipped, so a wrong-layout dequant whose shapes did not line up printed
    "p01 1.0000 [None]" and passed.
    """
    if not per_tensor:
        return NOTHING_INSPECTED, [
            "  compared 0 tensors: nothing was inspected, so this is not a pass.",
            "  (shape mismatch or non-2D everywhere is itself the wrong-layout signature)"]
    p01, name = min(per_tensor, key=lambda t: t[1])[1], min(per_tensor, key=lambda t: t[1])[0]
    lines = [f"  tensors compared           : {len(per_tensor)}",
             f"  worst per-row cosine (p01) : {p01:.4f}   [{name}]"]
    if p01 < threshold:
        lines += ["",
                  f"  BLOCKING: below {threshold}.",
                  "  -> read the checkpoint's actual scale layout instead of trusting the",
                  "     helper default. Linear (unswizzled) storage needs swizzle=False,",
                  "     then multiply by the fp32 global scale (weight_scale_2).",
                  "  -> keep embeddings, norms, conv1d and MTP/draft heads unquantized."]
        return BLOCKING, lines
    lines.append("  ok on weights. Now run the generation probes; weights alone are not enough.")
    return OK, lines


def evaluate_probes(results):
    """Pure core. `results` is a list of (probe_name, output_text). Empty is NOTHING_INSPECTED."""
    if not results:
        return NOTHING_INSPECTED, ["  ran 0 generation probes; nothing was inspected"]
    preds = {name: pred for name, _, pred in PROBES}
    lines, blocking = [], False
    for name, out in results:
        good = preds[name](out)
        blocking |= not good
        lines.append(f"  {name:9s}: {'ok' if good else 'BLOCKING'}  out={out[:60]!r}")
        if name == "nonempty" and not out.strip():
            lines.append("             immediate EOS is the classic wrong-layout signature")
    return (BLOCKING if blocking else OK), lines


def gen(base_url, model, prompt, timeout):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 64, "temperature": 0}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    txt = d["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()


def check_generation(base_url, model, timeout):
    results = []
    for name, prompt, _pred in PROBES:
        try:
            results.append((name, gen(base_url, model, prompt, timeout)))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  {name}: endpoint unreachable: {exc}", file=sys.stderr)
            return UNREACHABLE
    code, lines = evaluate_probes(results)
    print("\n".join(lines))
    return code


def check_weights(base_path, dq_path, sample_rows, threshold):
    try:
        import torch
        from safetensors import safe_open
    except ImportError:
        print("need torch + safetensors for weight mode", file=sys.stderr)
        return UNREACHABLE
    import glob
    import os

    def index(path):
        out = {}
        for f in sorted(glob.glob(os.path.join(path, "*.safetensors"))):
            with safe_open(f, framework="pt") as h:
                for k in h.keys():
                    out[k] = f
        return out

    try:
        bi, di = index(base_path), index(dq_path)
    except OSError as exc:
        print(f"cannot read checkpoints: {exc}", file=sys.stderr)
        return UNREACHABLE

    common = [k for k in bi if k in di and k.endswith(".weight")]
    per_tensor, skipped = [], 0
    for k in common:
        with safe_open(bi[k], framework="pt") as h:
            b = h.get_tensor(k)
        with safe_open(di[k], framework="pt") as h:
            d = h.get_tensor(k)
        if b.shape != d.shape or b.ndim != 2:
            skipped += 1
            continue
        n = min(sample_rows, b.shape[0])
        step = max(1, b.shape[0] // n)
        bb = b[::step][:n].to(torch.float64)
        dd = d[::step][:n].to(torch.float64)
        cos = torch.nn.functional.cosine_similarity(bb, dd, dim=1)
        per_tensor.append((k, torch.quantile(cos, 0.01).item()))

    if skipped:
        print(f"  skipped {skipped} tensor(s) on shape mismatch or non-2D")
    code, lines = evaluate_cosines(per_tensor, threshold)
    print("\n".join(lines))
    return code


# ---------------------------------------------------------------- contract controls

def _control_wrong_layout():
    """cosine 0.92, the swizzle=True case. MUST report BLOCKING."""
    return evaluate_cosines([("model.layers.0.mlp.down_proj.weight", 0.92),
                             ("model.layers.1.mlp.down_proj.weight", 0.95)], 0.995)[0]


def _control_probe_decimal_fails():
    """A dequant that answers the capital probe but fails the decimal probe."""
    return evaluate_probes([("capital", "Paris"),
                            ("decimal", "9 and 9"),
                            ("nonempty", "ok")])[0]


def _control_probe_immediate_eos():
    """Immediate EOS on every probe. MUST report BLOCKING."""
    return evaluate_probes([("capital", ""), ("decimal", ""), ("nonempty", "")])[0]


def _control_empty_tensors():
    """Every tensor skipped: the exact vacuous PASS this check shipped with."""
    return evaluate_cosines([], 0.995)[0]


NEGATIVE_CONTROLS = [
    ("wrong scale layout, cosine 0.92", _control_wrong_layout),
    ("capital probe passes but decimal probe fails", _control_probe_decimal_fails),
    ("immediate EOS on every probe", _control_probe_immediate_eos),
]
EMPTY_SET_CONTROL = ("zero tensors compared", _control_empty_tensors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--dequant")
    ap.add_argument("--sample-rows", type=int, default=4096)
    ap.add_argument("--threshold", type=float, default=0.995)
    ap.add_argument("--base-url")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    codes = []
    if a.base and a.dequant:
        codes.append(check_weights(a.base, a.dequant, a.sample_rows, a.threshold))
    if a.base_url:
        if not a.model:
            ap.error("--model is required with --base-url")
        codes.append(check_generation(a.base_url, a.model, a.timeout))
    if not codes:
        ap.error("pass --base/--dequant, or --base-url/--model, or both")

    for severity in (BLOCKING, UNREACHABLE, NOTHING_INSPECTED):
        if severity in codes:
            return severity
    print("\n  Reminder: a weight-only bf16 proxy (no runtime FP8 KV) is the OPTIMISTIC")
    print("  bound. Say so when publishing behavioral numbers measured on it.")
    return OK


if __name__ == "__main__":
    sys.exit(main())
