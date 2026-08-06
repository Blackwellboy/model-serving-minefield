#!/usr/bin/env python3
"""Check for traps 12, 16 and 22: is your ceiling truncating the reasoning tail?

Sends the same prompt N times at a fixed ceiling and reports the truncation rate plus the
completion-token distribution. A pileup at exactly the cap is the signature.

This is the distribution half of trap 12 step 4. Reasoning length at temp > 0 is
right-skewed, so a single value drawn from that distribution still truncates the tail
beyond it: a 9B measured 26% empty at the exact ceiling where its 35B-A3B sibling sat at
2.7%, and 9.1% were still empty after raising to 5120.

Run at your real eval temperature. At temp 0 you will not see the tail that bites at 0.6.
Trap 12 steps 1 and 2 come first: this probe is only meaningful once you know you are
looking at honest truncation and not degeneration.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 reasoning_budget_probe.py --base-url URL --model NAME --max-tokens 2560 -n 20 --temp 0.6
"""
import argparse
import json
import statistics
import sys
import urllib.error
import urllib.request

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

PROMPT = ("A team ships a service that must stay under 200ms p99. Walk through how you would "
          "decide between adding a cache, sharding the database, or rewriting the hot path, and "
          "state which you would do first and why.")


def evaluate(rows, max_tokens, max_empty_rate):
    """Pure core. `rows` is a list of dicts with finish_reason, content, completion_tokens."""
    if not rows:
        return NOTHING_INSPECTED, ["  0 samples collected; nothing was inspected"]

    n = len(rows)
    trunc = [r for r in rows if r.get("finish_reason") == "length"]
    empty = [r for r in rows if not (r.get("content") or "").strip()]
    toks = [r["completion_tokens"] for r in rows if r.get("completion_tokens") is not None]

    lines = [f"  budget                     : {max_tokens}",
             f"  truncated (finish=length)  : {len(trunc)}/{n} = {100*len(trunc)/n:.1f}%",
             f"  empty content              : {len(empty)}/{n} = {100*len(empty)/n:.1f}%"]

    true_empty = [r for r in rows
                  if not (r.get("content") or "").strip() and r.get("finish_reason") == "stop"]
    if true_empty:
        lines.append(f"  TRUE empties (finish=stop) : {len(true_empty)}  <- real signal, not artifact")

    if toks:
        ts = sorted(toks)
        p90 = ts[min(len(ts) - 1, int(0.9 * len(ts)))]
        at_cap = sum(1 for t in toks if t >= max_tokens)
        lines.append(f"  completion_tokens p50/p90/max: {statistics.median(ts):.0f} / {p90} / {max(ts)}")
        lines.append(f"  runs landing exactly at cap: {at_cap}  <- pileup at the cap = truncation")

    rate = len(empty) / n
    if rate > max_empty_rate:
        lines += ["",
                  f"  BLOCKING: empty rate {100*rate:.1f}% exceeds {100*max_empty_rate:.1f}%.",
                  "  -> mechanise trap 12 step 3 as retry-on-truncation (4096, 8192, 16384),",
                  "     not a bigger fixed ceiling; the tail can exceed any ceiling you pick.",
                  "  -> do NOT score these turns as refusals or failures."]
        return BLOCKING, lines
    lines.append("")
    lines.append(f"  ok: empty rate {100*rate:.1f}% within tolerance.")
    return OK, lines


def call(base_url, model, prompt, max_tokens, temp, timeout):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": temp, "top_p": 0.95}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    ch = d["choices"][0]
    return {"finish_reason": ch.get("finish_reason"),
            "content": ch["message"].get("content") or "",
            "completion_tokens": (d.get("usage") or {}).get("completion_tokens")}


# ---------------------------------------------------------------- contract controls

def _rows(n, finish, content, toks):
    return [{"finish_reason": finish, "content": content, "completion_tokens": toks}] * n


def _control_all_truncated():
    """Every sample truncated at the cap. MUST report BLOCKING."""
    return evaluate(_rows(20, "length", "", 2560), 2560, 0.02)[0]


def _control_quarter_empty():
    """The measured 26%-at-2560 case. MUST report BLOCKING."""
    rows = _rows(5, "length", "", 2560) + _rows(15, "stop", "a real answer", 1840)
    return evaluate(rows, 2560, 0.02)[0]


def _control_true_empties():
    """Clean stops with no content: real signal, and still blocking."""
    return evaluate(_rows(20, "stop", "", 400), 2560, 0.02)[0]


def _control_empty():
    """Zero samples. MUST NOT be a pass."""
    return evaluate([], 2560, 0.02)[0]


NEGATIVE_CONTROLS = [
    ("every sample truncated at the cap", _control_all_truncated),
    ("26% empty at the ceiling", _control_quarter_empty),
    ("clean stops with empty content", _control_true_empties),
]
EMPTY_SET_CONTROL = ("zero samples collected", _control_empty)


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
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  request {i+1}: endpoint unreachable: {exc}", file=sys.stderr)
            return UNREACHABLE
        print(f"\r  {i+1}/{a.n}", end="", flush=True)
    print()

    code, lines = evaluate(rows, a.max_tokens, a.max_empty_rate)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
