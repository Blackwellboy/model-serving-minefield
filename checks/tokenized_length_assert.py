#!/usr/bin/env python3
"""Trap 49 check: does your benchmark prompt tokenize to the length you named?

A `'AI. ' * 400` "4096-token" prompt tokenizes to 801, and a `[:4096]` slice on it is a
no-op. That mistake inflated a real 2-3x gap into a published 18x.

Every measurement here is COLD. An earlier version salted the prompt once and then grew
it, so the growth probes warmed the very prefix cache whose delta-reporting the check
exists to defeat, and the final measurement was warm on exactly the servers it targets.
Each probe now carries its own fresh salt.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 tokenized_length_assert.py --base-url URL --model NAME --target 4096
  python3 tokenized_length_assert.py --base-url URL --model NAME --target 4096 \
      --filler "AI. " --repeat 400        # reproduce a known-bad harness
"""
import argparse
import itertools
import json
import sys
import urllib.error
import urllib.request

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

_counter = itertools.count()


def fresh_salt():
    """A unique prefix per probe, so no measurement is served from a warm prefix."""
    return f"[probe {next(_counter)}-{id(object())}] "


def evaluate(measured, target, tolerance):
    """Pure core. `measured` is the server-reported token count, or None if never measured."""
    if measured is None:
        return NOTHING_INSPECTED, ["  no token count was obtained; nothing was inspected"]
    drift = (measured - target) / target
    lines = [f"  measured prompt tokens     : {measured}",
             f"  target                     : {target}",
             f"  drift                      : {drift*100:+.1f}%"]
    if abs(drift) > tolerance:
        lines += ["",
                  f"  BLOCKING: {measured} tokens against a target of {target}.",
                  "  -> the row is INVALID, not caveated. Build prompts by tokenizing to the",
                  "     target and decoding back, and record the achieved count next to the",
                  "     nominal one in every result row."]
        return BLOCKING, lines
    lines += ["", "  ok.",
              "  Cross-check against the server log's authoritative n_tokens line; a warm",
              "  request's prompt count may be the delta from the cached prefix."]
    return OK, lines


def post(url, body, timeout):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def count_tokens(base_url, model, text, timeout):
    """Prefer a real tokenize endpoint; fall back to usage on a COLD one-token request."""
    root = base_url.rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    try:
        d = post(root + "/tokenize", {"content": text}, timeout)
        toks = d.get("tokens")
        if isinstance(toks, list):
            return len(toks), "/tokenize"
    except Exception:
        pass
    body = {"model": model, "messages": [{"role": "user", "content": text}],
            "max_tokens": 1, "temperature": 0}
    d = post(base_url.rstrip("/") + "/chat/completions", body, timeout)
    return (d.get("usage") or {}).get("prompt_tokens"), "usage.prompt_tokens"


# ---------------------------------------------------------------- contract controls

def _control_the_801_case():
    """The real bug: 'AI. ' * 400 labelled 4096. MUST report BLOCKING."""
    return evaluate(801, 4096, 0.02)[0]


def _control_overshoot():
    """Drift in the other direction is equally invalid."""
    return evaluate(6000, 4096, 0.02)[0]


def _control_empty():
    """Never measured. MUST NOT be a pass."""
    return evaluate(None, 4096, 0.02)[0]


NEGATIVE_CONTROLS = [
    ("801 tokens labelled 4096", _control_the_801_case),
    ("6000 tokens labelled 4096", _control_overshoot),
]
EMPTY_SET_CONTROL = ("no token count obtained", _control_empty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--filler", default="The quick brown fox jumps over the lazy dog. ")
    ap.add_argument("--repeat", type=int, default=None,
                    help="fixed repeat count, to REPRODUCE a bad harness; omit to auto-grow")
    ap.add_argument("--tolerance", type=float, default=0.02)
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    try:
        if a.repeat is not None:
            body = a.filler * a.repeat
            body = body[:a.target]          # the classic no-op slice, faithfully reproduced
            prompt = fresh_salt() + body
        else:
            units = 1
            for _ in range(64):
                # fresh salt on EVERY probe: never measure a prefix we just warmed
                n, _src = count_tokens(a.base_url, a.model, fresh_salt() + a.filler * units,
                                       a.timeout)
                if n is None:
                    print("  server reported no token count", file=sys.stderr)
                    return UNREACHABLE
                if n >= a.target:
                    break
                units = max(units + 1, int(units * max(1.1, a.target / max(n, 1))))
            prompt = fresh_salt() + a.filler * units

        measured, src = count_tokens(a.base_url, a.model, prompt, a.timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  endpoint unreachable: {exc}", file=sys.stderr)
        return UNREACHABLE

    print(f"  built prompt               : {len(prompt)} chars")
    if measured is not None:
        print(f"  count source               : {src} (cold, freshly salted)")
    code, lines = evaluate(measured, a.target, a.tolerance)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
