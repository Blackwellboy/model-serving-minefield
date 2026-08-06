#!/usr/bin/env python3
"""Trap 48 check: is the latency you are blaming on the model actually client-side?

Compares client-observed latency against what the server itself says the request took,
and reports the unexplained gap. A large, roughly CONSTANT, client-only gap is not a model
problem: a dead IPv6 route on a dual-stack mDNS endpoint added ~30s to every request while
the server log showed 9.8s of real work.

Server total must include PREFILL. An earlier version of this check fell back to a
decode-only field when the total was absent, which books prompt-processing time into the
"client" gap and manufactures a false finding on long prefills. It now requires either a
genuine total, or prompt-plus-decode components that sum to one, or an operator-supplied
figure from the server log.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 latency_reconciliation.py --base-url http://HOST.local:8080/v1 --model NAME
  python3 latency_reconciliation.py --base-url http://127.0.0.1:8080/v1 --model NAME --server-total 9.8
"""
import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

PROMPT = "Reply with exactly the word: ok"


def server_total_seconds(payload):
    """Return (seconds, source) or (None, reason).

    Only accepts a figure that covers the WHOLE request. A decode-only field is
    explicitly rejected rather than silently used.
    """
    for key in ("timings", "timing"):
        t = payload.get(key)
        if not isinstance(t, dict):
            continue
        if "total_ms" in t:
            return float(t["total_ms"]) / 1000.0, "timings.total_ms"
        if "prompt_ms" in t and "predicted_ms" in t:
            return (float(t["prompt_ms"]) + float(t["predicted_ms"])) / 1000.0, \
                   "timings.prompt_ms + predicted_ms"
        if "predicted_ms" in t:
            return None, ("server reported only predicted_ms (decode). Using it as the "
                          "total would book prefill into the client gap; pass "
                          "--server-total from the server log instead")
    return None, "response carried no server-side timings"


def evaluate(client_times, server_total, max_gap):
    """Pure core. `client_times` is a list of per-call client latencies in seconds."""
    if not client_times:
        return NOTHING_INSPECTED, ["  0 calls timed; nothing was inspected"]
    if server_total is None:
        return NOTHING_INSPECTED, [
            "  server total unknown, so no reconciliation was performed.",
            "  This comparison IS the check; without both halves it inspected nothing."]

    client = sum(client_times) / len(client_times)
    gap = client - server_total
    spread = max(client_times) - min(client_times)
    lines = [f"  client latency (mean)  : {client:6.2f}s",
             f"  server total           : {server_total:6.2f}s",
             f"  unexplained gap        : {gap:6.2f}s"]
    if gap > max_gap:
        shape = "constant, smells like a resolution timeout" if spread < 2 else "variable"
        lines += ["",
                  f"  BLOCKING: {gap:.2f}s is client-side. Not the model, the quant, the KV",
                  "  cache type, the slot count or CUDA graphs, all of which were ruled out",
                  f"  before this was found. Gap spread across calls: {spread:.2f}s ({shape})."]
        return BLOCKING, lines
    lines += ["", "  ok: client and server agree."]
    return OK, lines


def timed_call(base_url, model, timeout):
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 8, "temperature": 0}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return time.perf_counter() - t0, d


def dual_stack_report(base_url):
    host = urllib.parse.urlparse(base_url).hostname
    if not host:
        return
    print(f"\n  resolution check for {host}:")
    try:
        fams = {info[0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        print(f"    getaddrinfo failed: {exc}")
        return
    has4, has6 = socket.AF_INET in fams, socket.AF_INET6 in fams
    print(f"    A record: {'yes' if has4 else 'no'}    AAAA record: {'yes' if has6 else 'no'}")
    if not (has4 and has6):
        print("    single-stack; this trap does not apply")
        return
    print("    DUAL-STACK. Timing each family separately:")
    if not shutil.which("curl"):
        print("    (curl not found; run: curl -6 -m 10 <url> ; curl -4 -m 10 <url>)")
        return
    url = base_url.rstrip("/") + "/models"
    for flag in ("-6", "-4"):
        t0 = time.perf_counter()
        rc = subprocess.run(["curl", flag, "-s", "-o", "/dev/null", "-m", "10", url],
                            capture_output=True).returncode
        print(f"      curl {flag}: {time.perf_counter()-t0:6.2f}s  "
              f"{'ok' if rc == 0 else f'FAILED (curl exit {rc})'}")
    print("    a v6 route that times out while v4 is instant is the cause; pin the IPv4 literal")


# ---------------------------------------------------------------- contract controls

def _control_thirty_second_gap():
    """The measured case: ~40s client, ~9.8s server. MUST report BLOCKING."""
    return evaluate([40.2, 40.1, 40.3], 9.8, 1.0)[0]


def _control_prefill_included_in_total():
    """A real total assembled from prompt_ms + predicted_ms still finds a real gap.

    Exercises the summing path that replaced the decode-only fallback.
    """
    total, _src = server_total_seconds({"timings": {"prompt_ms": 9400.0, "predicted_ms": 400.0}})
    return evaluate([40.2, 40.1, 40.3], total, 1.0)[0]


def _control_decode_only_not_accepted():
    """Regression guard for the defect this check shipped with.

    A decode-only figure must never be used as a server TOTAL: doing so books prefill
    into the client gap and manufactures a false finding on long prefills.

    Written so that CORRECT behaviour fails this control (as the contract requires) and
    the defect returning would make it pass, which the harness then reports as a
    violation. It is the regression that must be loud, not the current state.
    """
    total, _why = server_total_seconds({"timings": {"predicted_ms": 400.0}})
    if total is not None:
        return OK       # defect is back: harness flags "negative control PASSED"
    return BLOCKING     # correct: declined, so this control fails as it must


def _control_empty():
    """Zero calls timed. MUST NOT be a pass."""
    return evaluate([], 9.8, 1.0)[0]


NEGATIVE_CONTROLS = [
    ("30s client-only gap", _control_thirty_second_gap),
    ("prefill included via prompt_ms + predicted_ms", _control_prefill_included_in_total),
    ("decode-only timing declined as a total", _control_decode_only_not_accepted),
]
EMPTY_SET_CONTROL = ("zero calls timed", _control_empty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("--max-gap", type=float, default=1.0, help="seconds")
    ap.add_argument("--server-total", type=float, default=None,
                    help="seconds, from the server's own request log")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    client_times, server_totals, why = [], [], None
    for i in range(a.n):
        try:
            dt, payload = timed_call(a.base_url, a.model, a.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  endpoint unreachable: {exc}", file=sys.stderr)
            return UNREACHABLE
        client_times.append(dt)
        s, src = server_total_seconds(payload)
        if s is not None:
            server_totals.append(s)
        else:
            why = src
        print(f"  call {i+1}: client {dt:6.2f}s" + (f"   server {s:6.2f}s ({src})" if s else ""))

    server_total = (sum(server_totals) / len(server_totals)) if server_totals else a.server_total
    if server_total is None and why:
        print(f"\n  no usable server total: {why}")

    code, lines = evaluate(client_times, server_total, a.max_gap)
    print("\n".join(lines))
    if code in (BLOCKING, NOTHING_INSPECTED):
        dual_stack_report(a.base_url)
    return code


if __name__ == "__main__":
    sys.exit(main())
