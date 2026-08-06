#!/usr/bin/env python3
"""Trap 47 check: is the prefix cache actually engaging on a growing conversation?

Sends a growing conversation with a large stable prefix and reports time-to-first-token per
turn, plus any server-reported cached-token count. On a caching engine TTFT collapses after
turn 1. Flat TTFT means the cache is not engaging: either the engine auto-disabled it for
this architecture (vLLM does that for hybrid mamba/DeltaNet and says so once, at startup),
or something in your prefix changes per message.

Two corrections over the first version. `stream_options.include_usage` is now requested, so
the `cached_tokens` corroboration actually fires on vLLM-dialect servers instead of never
arriving. And flat TTFT alone is reported as INCONCLUSIVE rather than as a finding: TTFT is
a noisy proxy, and a short prefix or a fast box can hide a working cache. It is a finding
only when the server itself reports a cached fraction that stays near zero.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 cache_hit_probe.py --base-url URL --model NAME --turns 3
  grep -i enable_prefix_caching server.log      # the one-line version, if you have the log
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

PREFIX = ("You are a build assistant. Reference material follows.\n"
          + "".join(f"- rule {i}: prefer the simplest change that passes the tests.\n"
                    for i in range(400)))


def evaluate(turns):
    """Pure core. `turns` is a list of dicts: {ttft, cached, prompt_tokens}.

    cached/prompt_tokens are None when the server reported no usage.
    """
    if len(turns) < 2:
        return NOTHING_INSPECTED, [
            f"  {len(turns)} turn(s) captured; at least 2 are needed to compare. "
            "Nothing was inspected."]

    ttfts = [t["ttft"] for t in turns]
    drop = (ttfts[0] - min(ttfts[1:])) / ttfts[0] if ttfts[0] else 0.0
    lines = [f"  TTFT drop after turn 1 : {drop*100:.1f}%"]

    ratios = [t["cached"] / t["prompt_tokens"]
              for t in turns[1:]
              if t.get("cached") is not None and t.get("prompt_tokens")]

    if ratios:
        best = max(ratios)
        lines.append(f"  best server-reported cached fraction : {best*100:.0f}%")
        if best < 0.5:
            lines += ["",
                      "  BLOCKING: the server itself reports the prefix is not being reused.",
                      "  -> check the startup log for `enable_prefix_caching=False` (auto-disabled",
                      "     for hybrid mamba/DeltaNet archs; not overridable).",
                      "  -> if the engine DOES cache, something in your prefix changes per message:",
                      "     look for client-side attribution or metadata headers.",
                      "  -> until this is resolved, do not publish an agentic throughput",
                      "     comparison; you are measuring two different workloads."]
            return BLOCKING, lines
        lines += ["", "  ok: the prefix cache is engaging."]
        return OK, lines

    # No usage reported: TTFT alone is a proxy, not a verdict.
    lines.append("  server reported no cached-token usage (include_usage unsupported?)")
    if drop < 0.25:
        lines += ["",
                  "  INCONCLUSIVE: flat TTFT, and no server-side cache accounting to confirm it.",
                  "  TTFT is a noisy proxy: a short prefix or a fast box hides a working cache.",
                  "  Read the startup log for `enable_prefix_caching`, or re-run against a server",
                  "  that reports prompt_tokens_details.cached_tokens."]
        return NOTHING_INSPECTED, lines
    lines += ["", "  ok: TTFT collapsed after turn 1, consistent with a working cache."]
    return OK, lines


def ttft_call(base_url, model, messages, timeout):
    body = {"model": model, "messages": messages, "max_tokens": 32, "temperature": 0,
            "stream": True, "stream_options": {"include_usage": True}}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    first, text, cached, prompt_tokens = None, [], None, None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                d = json.loads(payload)
            except json.JSONDecodeError:
                continue
            usage = d.get("usage") or {}
            if usage:
                prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                details = usage.get("prompt_tokens_details") or {}
                if "cached_tokens" in details:
                    cached = details["cached_tokens"]
            delta = (d.get("choices") or [{}])[0].get("delta", {}).get("content") if d.get("choices") else None
            if delta:
                if first is None:
                    first = time.perf_counter() - t0
                text.append(delta)
    return {"ttft": first if first is not None else time.perf_counter() - t0,
            "text": "".join(text), "cached": cached, "prompt_tokens": prompt_tokens}


# ---------------------------------------------------------------- contract controls

def _t(ttft, cached=None, prompt_tokens=None):
    return {"ttft": ttft, "cached": cached, "prompt_tokens": prompt_tokens}


def _control_server_reports_no_reuse():
    """Server accounting says the prefix is not reused. MUST report BLOCKING."""
    return evaluate([_t(5.48, 0, 6000), _t(5.51, 0, 6100), _t(5.55, 0, 6200)])[0]


def _control_fast_ttft_but_no_reuse():
    """TTFT looks fine, but the server says nothing is cached: accounting wins."""
    return evaluate([_t(5.00, 0, 6000), _t(0.20, 0, 6100), _t(0.19, 0, 6200)])[0]


def _control_single_turn():
    """One turn cannot show a drop. MUST NOT be a pass."""
    return evaluate([_t(5.0, 6000, 6000)])[0]


NEGATIVE_CONTROLS = [
    ("server reports 0% cached across turns", _control_server_reports_no_reuse),
    ("fast TTFT but zero reported reuse", _control_fast_ttft_but_no_reuse),
]
EMPTY_SET_CONTROL = ("fewer than two turns captured", _control_single_turn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    messages, turns = [{"role": "system", "content": PREFIX}], []
    for i in range(a.turns):
        messages.append({"role": "user", "content": f"Question {i+1}: name one rule, briefly."})
        try:
            t = ttft_call(a.base_url, a.model, messages, a.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  endpoint unreachable: {exc}", file=sys.stderr)
            return UNREACHABLE
        turns.append(t)
        extra = ""
        if t["cached"] is not None and t["prompt_tokens"]:
            extra = f"   cached {t['cached']}/{t['prompt_tokens']} = {100*t['cached']/t['prompt_tokens']:.0f}%"
        print(f"  turn {i+1} TTFT {t['ttft']:6.2f}s{extra}")
        messages.append({"role": "assistant", "content": t["text"].strip() or "ok"})

    code, lines = evaluate(turns)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
