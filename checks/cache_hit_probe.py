#!/usr/bin/env python3
"""Trap 48 check, is the prefix cache actually engaging on a growing conversation?

Sends a growing multi-turn conversation with a large stable prefix and reports time-to-first-token
per turn. On a caching engine TTFT collapses after turn 1 and any server-reported cache ratio
climbs toward 97-100%. Flat TTFT means the cache is not engaging, either the engine
auto-disabled it for this architecture (vLLM does this for hybrid mamba/DeltaNet and says so
once, at startup) or something in your prefix changes per message.

Also usable for the client-side sibling (a client that prepends per-message headers invalidates the prefix and
turns generation into O(N^2)), same symptom, different cause, same probe.

Exit 0 = TTFT falls after turn 1, 1 = flat, 2 = could not run.

Usage:
  python3 cache_hit_probe.py --base-url http://127.0.0.1:8080/v1 --model my-model --turns 3
  grep -i enable_prefix_caching server.log     # the one-line version, if you have the log
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# A large, stable prefix is what a cache would hit on.
PREFIX = ("You are a build assistant. Reference material follows.\n"
          + "".join(f"- rule {i}: prefer the simplest change that passes the tests.\n"
                    for i in range(400)))


def ttft(base_url, model, messages, timeout):
    """Streamed first-token latency; falls back to whole-response latency if not streaming."""
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 32,
        "temperature": 0,
        "stream": True,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    first = None
    text = []
    cached = None
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
            details = usage.get("prompt_tokens_details") or {}
            if "cached_tokens" in details:
                cached = (details["cached_tokens"], usage.get("prompt_tokens"))
            delta = (d.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                if first is None:
                    first = time.perf_counter() - t0
                text.append(delta)
    return first if first is not None else (time.perf_counter() - t0), "".join(text), cached


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    messages = [{"role": "system", "content": PREFIX}]
    times = []
    for i in range(a.turns):
        messages.append({"role": "user", "content": f"Question {i+1}: name one rule, briefly."})
        try:
            t, reply, cached = ttft(a.base_url, a.model, messages, a.timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        times.append(t)
        extra = ""
        if cached:
            c, p = cached
            extra = f"   cached {c}/{p}" + (f" = {100*c/p:.0f}%" if p else "")
        print(f"  turn {i+1} TTFT {t:6.2f}s{extra}")
        messages.append({"role": "assistant", "content": reply.strip() or "ok"})

    if len(times) < 2:
        return 2

    drop = (times[0] - min(times[1:])) / times[0]
    print(f"\n  TTFT drop after turn 1 : {drop*100:.1f}%")
    if drop < 0.25:
        print("\n  FAIL: flat TTFT, the prefix cache is not engaging.")
        print("  -> check the startup log for `enable_prefix_caching=False` (auto-disabled for")
        print("     hybrid mamba/DeltaNet archs in vLLM 0.24-era builds; not overridable).")
        print("  -> if the engine DOES cache, something in your prefix changes per message:")
        print("     look for client-side attribution/metadata headers (O(N) -> O(N^2)).")
        print("  -> until this is resolved, do not publish an 'agentic throughput' comparison;")
        print("     you are measuring two different workloads.")
        return 1

    print("\n  PASS: cache is engaging.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
