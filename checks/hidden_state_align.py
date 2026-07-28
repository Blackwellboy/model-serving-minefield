#!/usr/bin/env python3
"""Trap 51 check, are your per-layer dumps aligned with the reference's dump convention?

Before filing a "layer N exploded" bug, prove the two dumps mean the same thing. Custom
HuggingFace modeling files (trust_remote_code) set `output_hidden_states` semantics themselves;
one such file appends at the TOP of the layer loop, so hs[i] is the INPUT to layer i, and the
final entry is POST final-norm. Comparing that against a pre-norm dump at the same index
manufactures a 4.5x "explosion" in a correct implementation.

This script:
  1. asserts the dump COUNTS are consistent (53 reference entries for 52 layers is the tell)
  2. tries both index alignments and reports which one is coherent
  3. checks whether a reported "collapse" simply lands on ||norm_f.weight||, which is what
     RMSNorm does to any input by construction

Exit 0 = an alignment was found, 1 = genuinely divergent, 2 = could not run.

Usage:
  python3 hidden_state_align.py --ours ./dumps/ours --ref ./dumps/ref \
      --pattern-ours 'p0_layer{n}.bin' --pattern-ref 'hs_{n}.bin' \
      --norm-weight ./dumps/norm_f_weight.bin --dtype float32
"""
import argparse
import glob
import os
import re
import sys

try:
    import numpy as np
except ImportError:
    print("need numpy", file=sys.stderr)
    sys.exit(2)


def load(path, dtype):
    return np.fromfile(path, dtype=dtype).astype(np.float64)


def collect(d, pattern, dtype):
    rx = re.compile(re.escape(pattern).replace(r"\{n\}", r"(\d+)"))
    out = {}
    for p in glob.glob(os.path.join(d, "*")):
        m = rx.fullmatch(os.path.basename(p))
        if m:
            out[int(m.group(1))] = load(p, dtype)
    return out


def cos(a, b):
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    da, db = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (da * db)) if da and db else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--pattern-ours", default="layer{n}.bin")
    ap.add_argument("--pattern-ref", default="hs_{n}.bin")
    ap.add_argument("--norm-weight")
    ap.add_argument("--dtype", default="float32")
    a = ap.parse_args()

    dt = np.dtype(a.dtype)
    ours = collect(a.ours, a.pattern_ours, dt)
    ref = collect(a.ref, a.pattern_ref, dt)
    if not ours or not ref:
        print("no dumps matched the patterns", file=sys.stderr)
        return 2

    print(f"  ours: {len(ours)} dumps (idx {min(ours)}..{max(ours)})")
    print(f"  ref : {len(ref)} dumps (idx {min(ref)}..{max(ref)})")
    if len(ref) == len(ours) + 1:
        print("  -> ref has exactly one MORE entry than ours. That is the off-by-one tell:")
        print("     the reference likely appends at the TOP of the layer loop (hs[i] = input")
        print("     to layer i) and appends a final POST-norm state after the loop.")

    print("\n  norm ladder (ours vs ref at both alignments):")
    print(f"  {'idx':>4} {'||ours||':>10} {'||ref[i]||':>11} {'||ref[i+1]||':>13}")
    for i in sorted(ours)[-6:]:
        no = np.linalg.norm(ours[i])
        nr = np.linalg.norm(ref[i]) if i in ref else float("nan")
        nr1 = np.linalg.norm(ref[i + 1]) if (i + 1) in ref else float("nan")
        print(f"  {i:>4} {no:10.1f} {nr:11.1f} {nr1:13.1f}")

    best = None
    for shift in (0, 1, -1):
        pairs = [(ours[i], ref[i + shift]) for i in ours if (i + shift) in ref]
        if len(pairs) < 3:
            continue
        # skip the last layer: pre-norm vs post-norm is expected to disagree
        scores = [cos(o, r) for o, r in pairs[:-1]]
        mean = sum(scores) / len(scores)
        print(f"\n  alignment ours[L] <-> ref[L{shift:+d}] : mean cosine {mean:.4f} over {len(scores)} layers")
        if best is None or mean > best[1]:
            best = (shift, mean)

    if a.norm_weight:
        w = load(a.norm_weight, dt)
        nw = float(np.linalg.norm(w))
        print(f"\n  ||norm_f.weight|| = {nw:.2f}")
        print("  RMSNorm maps ANY input to about this value, so a post-norm state landing here")
        print("  is arithmetic, not a collapse. If the reference's 'drop' lands on this number,")
        print("  you are comparing a pre-norm state against a post-norm one.")

    if best is None:
        print("\n  could not evaluate any alignment", file=sys.stderr)
        return 2

    shift, mean = best
    if mean >= 0.99:
        print(f"\n  PASS: ours[L] <-> ref[L{shift:+d}] is the correct alignment (mean cos {mean:.4f}).")
        print("  Fix the HARNESS, not the model. Apply your final norm before comparing your")
        print("  last layer to the reference's final entry.")
        return 0

    print(f"\n  FAIL: best alignment only reaches mean cosine {mean:.4f}.")
    print("  Before concluding your implementation is wrong: is the reference bf16 while yours")
    print("  is f32? bf16 is imprecise for RMSNorm over outliers, so cosine-vs-bf16 PENALIZES")
    print("  accuracy. Re-run the reference in f32, and prefer top-k logit overlap and softmax")
    print("  KL over raw-logit cosine.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
