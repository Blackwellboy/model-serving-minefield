#!/usr/bin/env python3
"""Trap 44 check, is your `max_tokens` truncating the reasoning tail?

Sends the SAME prompt N times at a fixed budget and reports the truncation rate plus the
completion-token distribution. A pileup at exactly the cap is the signature: the empty rate
you are about to score as behavior is a budget-vs-variance artifact.

Reasoning length at temp>0 is right-skewed, so this must be run at your real eval temperature,
not at 0. Run it once per model size, a budget tuned on a large model manufactures phantom
failures on a small one (measured: 26% empties on a 9B at the exact budget where its 35B
sibling sat at 2.7%).

Exit 0 = truncation rate under --max-empty-rate, 1 = over, 2 = could not run.

Usage:
  python3 reasoning_budget_probe.py --base-url http://127.0.0.1:8080/v1 \
      --model my-model --max-tokens 2560 -n 20 --temp 0.6
  # then re-run with --max-tokens 8192 and compare
"""
import argparse
import json
import statistics
import sys
import urllib.error
import urllib.request

PROMPT = (
    "A team ships a service that must stay under 200ms p99. Walk through how you would "
    "decide between adding a cache, sharding the database, or rewriting the hot path, and "
    "state which you would do first and why."
)


def call(base_url, model, prompt, max_tokens, temp, timeout):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temp,
        "top_p": 0.95,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    ch = d["choices"][0]
    msg = ch["message"]
    return {
        "finish_reason": ch.get("finish_reason"),
        "content": (msg.get("content") or "").strip(),
        "reasoning": (msg.get("reasoning_content") or "") or "",
        "completion_tokens": (d.get("usage") or {}).get("completion_tokens"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-tokens", type=int, required=True)
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--temp", type=float, default=0.6)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--max-empty-rate", type=float, default=0.02)
    a = ap.parse_args()

    rows = []
    for i in range(a.n):
        try:
            rows.append(call(a.base_url, a.model, PROMPT, a.max_tokens, a.temp, a.timeout))
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  request {i+1}: ERROR {exc}", file=sys.stderr)
            return 2
        print(f"\r  {i+1}/{a.n}", end="", flush=True)
    print()

    trunc = [r for r in rows if r["finish_reason"] == "length"]
    empty = [r for r in rows if not r["content"]]
    toks = [r["completion_tokens"] for r in rows if r["completion_tokens"] is not None]

    print(f"\n  budget                     : {a.max_tokens} @ temp {a.temp}")
    print(f"  truncated (finish=length)  : {len(trunc)}/{a.n} = {100*len(trunc)/a.n:.1f}%")
    print(f"  empty content              : {len(empty)}/{a.n} = {100*len(empty)/a.n:.1f}%")

    true_empty = [r for r in rows if not r["content"] and r["finish_reason"] == "stop"]
    if true_empty:
        print(f"  TRUE empties (finish=stop) : {len(true_empty)} <- real signal, not artifact")

    if toks:
        toks_sorted = sorted(toks)
        p50 = statistics.median(toks_sorted)
        p90 = toks_sorted[min(len(toks_sorted) - 1, int(0.9 * len(toks_sorted)))]
        at_cap = sum(1 for t in toks if t >= a.max_tokens)
        print(f"  completion_tokens p50/p90/max: {p50:.0f} / {p90} / {max(toks)}")
        print(f"  runs landing exactly at cap: {at_cap}  <- pileup at the cap = truncation")

    rate = len(empty) / a.n
    if rate > a.max_empty_rate:
        print(f"\n  FAIL: empty rate {100*rate:.1f}% exceeds {100*a.max_empty_rate:.1f}%.")
        print("  -> implement retry-on-truncation (4096 -> 8192 -> 16384), not a bigger fixed")
        print("     budget; the tail can exceed any ceiling (9.1% empties survived at 5120).")
        print("  -> do NOT score these turns as refusals or failures.")
        return 1

    print(f"\n  PASS: empty rate {100*rate:.1f}% within tolerance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
