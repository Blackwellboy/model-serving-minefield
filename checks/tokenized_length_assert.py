#!/usr/bin/env python3
"""Trap 50 check, does your benchmark prompt actually tokenize to the length you named?

Builds a filler prompt the way benchmark harnesses usually do, sends it COLD, and asserts the
server's own reported prompt-token count against the target. A `'AI. ' * 400` "4096-token"
prompt tokenizes to 801; a `[:4096]` slice on it is a no-op. That mistake inflated a real
2-3x gap into a published 18x.

Must be run COLD: on some servers the API's prompt-token field is the delta from the cached
prefix, not the absolute length, so a warm request under-reports. This script salts the prompt
with a unique prefix each run to defeat the cache.

Exit 0 = within tolerance, 1 = mismatch, 2 = could not run.

Usage:
  python3 tokenized_length_assert.py --base-url http://127.0.0.1:8080/v1 \
      --model my-model --target 4096
  python3 tokenized_length_assert.py ... --filler "AI. " --repeat 400   # reproduce the bug
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def post(url, body, timeout):
    req = urllib.request.Request(
        url, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def count_via_tokenize(base_url, model, text, timeout):
    """Prefer a real tokenize endpoint when the server exposes one."""
    root = base_url.rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    try:
        d = post(root + "/tokenize", {"content": text}, timeout)
        toks = d.get("tokens")
        if isinstance(toks, list):
            return len(toks), "/tokenize"
    except Exception:
        pass
    return None, None


def count_via_usage(base_url, model, text, timeout):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": 1,
        "temperature": 0,
    }
    d = post(base_url.rstrip("/") + "/chat/completions", body, timeout)
    usage = d.get("usage") or {}
    return usage.get("prompt_tokens"), "usage.prompt_tokens"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--filler", default="The quick brown fox jumps over the lazy dog. ")
    ap.add_argument("--repeat", type=int, default=None,
                    help="fixed repeat count (use to REPRODUCE a bad harness); "
                         "omit to auto-grow until the target is hit")
    ap.add_argument("--tolerance", type=float, default=0.02)
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    salt = f"[run {time.time_ns()}] "  # defeat prompt cache so the count is absolute

    if a.repeat is not None:
        prompt = salt + a.filler * a.repeat
        prompt = prompt[: a.target]  # the classic no-op slice, faithfully reproduced
    else:
        # grow until measured tokens reach the target
        prompt = salt + a.filler
        for _ in range(64):
            n, _src = count_via_tokenize(a.base_url, a.model, prompt, a.timeout)
            if n is None:
                try:
                    n, _src = count_via_usage(a.base_url, a.model, prompt, a.timeout)
                except (urllib.error.URLError, TimeoutError) as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    return 2
            if n is None:
                print("ERROR: server reported no token count", file=sys.stderr)
                return 2
            if n >= a.target:
                break
            grow = max(1, int((a.target - n) / max(1, n / max(1, prompt.count(a.filler)))))
            prompt += a.filler * grow

    n, src = count_via_tokenize(a.base_url, a.model, prompt, a.timeout)
    if n is None:
        try:
            n, src = count_via_usage(a.base_url, a.model, prompt, a.timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    drift = (n - a.target) / a.target
    print(f"  built prompt               : {len(prompt)} chars")
    print(f"  measured prompt tokens     : {n}   (source: {src})")
    print(f"  target                     : {a.target}")
    print(f"  drift                      : {drift*100:+.1f}%")

    if abs(drift) > a.tolerance:
        print(f"\n  FAIL: {n} tokens vs target {a.target}.")
        print("  -> the row is INVALID, not caveated. Build prompts by tokenizing to the")
        print("     target and decoding back, and record the achieved count next to the")
        print("     nominal one in every result row.")
        return 1

    print("\n  PASS.")
    print("  Reminder: also cross-check against the server log's authoritative n_tokens line;")
    print("  a warm request's prompt count may be the delta from the cached prefix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
