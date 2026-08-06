#!/usr/bin/env python3
"""Trap 50 check: are your per-layer dumps aligned with the reference's dump convention?

Before filing a "layer N exploded" bug against your own implementation, prove the two dumps
mean the same thing. A custom HF modeling file appended hidden states at the TOP of the
layer loop, so hs[i] is the INPUT to layer i, and its final entry is POST final-norm.
Comparing that against a pre-norm dump at the same index manufactured a 4.5x "explosion"
in a correct implementation.

Ordering is explicit throughout. An earlier version iterated dict insertion order (which
comes from glob order, not layer order) and then dropped `pairs[:-1]`, so it discarded an
arbitrary pair rather than the final layer, which is the one pair that is SUPPOSED to
disagree.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 hidden_state_align.py --ours DIR --ref DIR \
      --pattern-ours 'p0_layer{n}.bin' --pattern-ref 'hs_{n}.bin' \
      --norm-weight ./dumps/norm_f_weight.bin --dtype float32
"""
import argparse
import glob
import os
import re
import sys

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

try:
    import numpy as np
except ImportError:
    np = None


def cos(a, b):
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    da, db = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (da * db)) if da and db else 0.0


def evaluate(alignments, n_ours, n_ref):
    """Pure core. `alignments` maps a shift to a mean cosine over comparable layers.

    Empty means no alignment could be evaluated: NOTHING_INSPECTED, never OK.
    """
    lines = [f"  ours: {n_ours} dumps    ref: {n_ref} dumps"]
    if n_ref == n_ours + 1:
        lines += ["  -> ref has exactly one MORE entry than ours. That is the off-by-one tell:",
                  "     the reference likely appends at the TOP of the layer loop (hs[i] = input",
                  "     to layer i) and appends a final POST-norm state after the loop."]
    if not alignments:
        lines.append("  no alignment could be evaluated; nothing was inspected")
        return NOTHING_INSPECTED, lines

    for shift in sorted(alignments):
        lines.append(f"  alignment ours[L] to ref[L{shift:+d}] : mean cosine {alignments[shift]:.4f}")
    shift, mean = max(alignments.items(), key=lambda kv: kv[1])
    if mean >= 0.99:
        lines += ["",
                  f"  ok: ours[L] to ref[L{shift:+d}] is the correct alignment (mean cos {mean:.4f}).",
                  "  Fix the HARNESS, not the model. Apply your final norm before comparing your",
                  "  last layer to the reference's final entry."]
        return OK, lines
    lines += ["",
              f"  BLOCKING: best alignment only reaches mean cosine {mean:.4f}.",
              "  Before concluding your implementation is wrong: is the reference bf16 while",
              "  yours is f32? bf16 is imprecise for RMSNorm over outliers, so cosine-vs-bf16",
              "  PENALIZES accuracy. Re-run the reference in f32, and prefer top-k logit",
              "  overlap and softmax KL over raw-logit cosine."]
    return BLOCKING, lines


def collect(d, pattern, dtype):
    rx = re.compile(re.escape(pattern).replace(r"\{n\}", r"(\d+)"))
    out = {}
    for p in glob.glob(os.path.join(d, "*")):
        m = rx.fullmatch(os.path.basename(p))
        if m:
            out[int(m.group(1))] = np.fromfile(p, dtype=dtype).astype(np.float64)
    return out


def alignments_from(ours, ref):
    """Mean cosine per shift, over layers sorted by INDEX, excluding the highest index.

    The final layer is excluded deliberately: pre-norm against post-norm is expected to
    disagree there, and including it would mask a genuine misalignment elsewhere.
    """
    result = {}
    for shift in (0, 1, -1):
        idx = sorted(i for i in ours if (i + shift) in ref)
        if len(idx) < 3:
            continue
        comparable = idx[:-1]          # drop the HIGHEST index, by sort order, not dict order
        scores = [cos(ours[i], ref[i + shift]) for i in comparable]
        result[shift] = sum(scores) / len(scores)
    return result


# ---------------------------------------------------------------- contract controls

def _control_offbyone():
    """A misaligned harness: only the +1 shift is coherent, and we hand in the 0 shift."""
    return evaluate({0: 0.61}, 52, 53)[0]


def _control_all_poor():
    """Every alignment poor. MUST report BLOCKING."""
    return evaluate({0: 0.55, 1: 0.60, -1: 0.42}, 52, 52)[0]


def _control_empty():
    """No alignment evaluable. MUST NOT be a pass."""
    return evaluate({}, 0, 0)[0]


NEGATIVE_CONTROLS = [
    ("only the misaligned shift offered", _control_offbyone),
    ("no shift reaches parity", _control_all_poor),
]
EMPTY_SET_CONTROL = ("no alignment evaluable", _control_empty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--pattern-ours", default="layer{n}.bin")
    ap.add_argument("--pattern-ref", default="hs_{n}.bin")
    ap.add_argument("--norm-weight")
    ap.add_argument("--dtype", default="float32")
    a = ap.parse_args()

    if np is None:
        print("need numpy", file=sys.stderr)
        return UNREACHABLE

    dt = np.dtype(a.dtype)
    try:
        ours = collect(a.ours, a.pattern_ours, dt)
        ref = collect(a.ref, a.pattern_ref, dt)
    except OSError as exc:
        print(f"cannot read dumps: {exc}", file=sys.stderr)
        return UNREACHABLE

    if ours and ref:
        print("\n  norm ladder (highest indices, by sort order):")
        print(f"  {'idx':>4} {'||ours||':>10} {'||ref[i]||':>11} {'||ref[i+1]||':>13}")
        for i in sorted(ours)[-6:]:
            no = np.linalg.norm(ours[i])
            nr = np.linalg.norm(ref[i]) if i in ref else float("nan")
            nr1 = np.linalg.norm(ref[i + 1]) if (i + 1) in ref else float("nan")
            print(f"  {i:>4} {no:10.1f} {nr:11.1f} {nr1:13.1f}")

    if a.norm_weight:
        try:
            nw = float(np.linalg.norm(np.fromfile(a.norm_weight, dtype=dt).astype(np.float64)))
            print(f"\n  ||norm_f.weight|| = {nw:.2f}")
            print("  RMSNorm maps ANY input to about this value, so a post-norm state landing")
            print("  here is arithmetic, not a collapse. If the reference's 'drop' lands on")
            print("  this number, you are comparing a pre-norm state against a post-norm one.")
        except OSError as exc:
            print(f"  (could not read --norm-weight: {exc})")

    code, lines = evaluate(alignments_from(ours, ref), len(ours), len(ref))
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
