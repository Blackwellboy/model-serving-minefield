#!/usr/bin/env python3
"""Trap 45 check, did your offline dequant use the right scale layout?

Two assertions, because either alone passes on a subtly-broken model:

  1. PER-ROW cosine in float64 between the dequantized weights and the base weights.
     A FLAT cosine over a 1.27B-element lm_head overflows in float32 and can return > 1 , 
     which is itself the tell that your metric is broken, not your weights.
  2. Generation probes. The capital-of-France probe PASSES on a wrong-layout dequant.
     The decimal-comparison probe does not. Run both.

Reference points from the case that produced this entry:
  swizzle=True  -> cosine 0.92   : immediate EOS, "9.9 vs 9.11" -> "9 and 9", mangled tokens
  swizzle=False -> cosine 0.9967 : coherent

cosine 0.92 is a DESTROYED 64-layer model, not a close one.

Exit 0 = pass, 1 = fail, 2 = could not run.

Usage:
  # weights only (needs torch + safetensors)
  python3 dequant_fidelity.py --base /path/base --dequant /path/out --sample-rows 4096
  # generation probes against a served endpoint (stdlib only)
  python3 dequant_fidelity.py --base-url http://127.0.0.1:8000/v1 --model my-model
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

PROBES = [
    ("capital", "What is the capital of France? Answer with one word.",
     lambda s: "paris" in s.lower()),
    ("decimal", "Which is larger, 9.9 or 9.11? Answer with just the number.",
     lambda s: "9.9" in s and "9.11" not in s.split("9.9")[0]),
    ("nonempty", "Say the word: ok", lambda s: len(s.strip()) > 0),
]


def gen(base_url, model, prompt, timeout):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
        "temperature": 0,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    msg = d["choices"][0]["message"]
    txt = msg.get("content") or ""
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip(), \
        d["choices"][0].get("finish_reason")


def check_generation(base_url, model, timeout):
    ok = True
    for name, prompt, pred in PROBES:
        try:
            out, finish = gen(base_url, model, prompt, timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  {name:9s}: ERROR {exc}", file=sys.stderr)
            return 2
        good = pred(out)
        ok &= good
        print(f"  {name:9s}: {'PASS' if good else 'FAIL'}  finish={finish!r}  out={out[:60]!r}")
        if name == "nonempty" and not out:
            print("             immediate-EOS is the classic wrong-scale-layout signature")
    return 0 if ok else 1


def check_weights(base_path, dq_path, sample_rows, threshold):
    try:
        import torch
        from safetensors import safe_open
    except ImportError:
        print("need torch + safetensors for weight mode", file=sys.stderr)
        return 2
    import glob
    import os

    def index(path):
        out = {}
        for f in sorted(glob.glob(os.path.join(path, "*.safetensors"))):
            with safe_open(f, framework="pt") as h:
                for k in h.keys():
                    out[k] = f
        return out

    bi, di = index(base_path), index(dq_path)
    common = [k for k in bi if k in di and k.endswith(".weight")]
    if not common:
        print("no common .weight tensors found", file=sys.stderr)
        return 2

    worst = (1.0, None)
    for k in common:
        with safe_open(bi[k], framework="pt") as h:
            b = h.get_tensor(k)
        with safe_open(di[k], framework="pt") as h:
            d = h.get_tensor(k)
        if b.shape != d.shape or b.ndim != 2:
            continue
        n = min(sample_rows, b.shape[0])
        step = max(1, b.shape[0] // n)
        # float64, PER ROW, never a flat cosine over the whole tensor
        bb = b[::step][:n].to(torch.float64)
        dd = d[::step][:n].to(torch.float64)
        cos = torch.nn.functional.cosine_similarity(bb, dd, dim=1)
        p01 = torch.quantile(cos, 0.01).item()
        if p01 < worst[0]:
            worst = (p01, k)

    p01, name = worst
    print(f"  worst per-row cosine (p01) : {p01:.4f}   [{name}]")
    if p01 < threshold:
        print(f"\n  FAIL: below {threshold}.")
        print("  -> read the checkpoint's actual scale layout instead of trusting the helper")
        print("     default. Linear (unswizzled) storage needs swizzle=False, then multiply")
        print("     by the fp32 global scale (weight_scale_2).")
        print("  -> keep embeddings, norms, conv1d and MTP/draft heads unquantized.")
        return 1
    print("\n  PASS on weights. Now run the generation probes, weights alone are not enough.")
    return 0


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

    rc = 0
    if a.base and a.dequant:
        rc |= check_weights(a.base, a.dequant, a.sample_rows, a.threshold)
    if a.base_url:
        if not a.model:
            ap.error("--model is required with --base-url")
        rc |= check_generation(a.base_url, a.model, a.timeout)
    if not (a.base and a.dequant) and not a.base_url:
        ap.error("pass --base/--dequant, or --base-url/--model, or both")

    if rc == 0:
        print("\n  Reminder: a weight-only bf16 proxy (no runtime FP8 KV) is the OPTIMISTIC")
        print("  bound. Say so when publishing behavioral numbers measured on it.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
