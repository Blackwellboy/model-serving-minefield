#!/usr/bin/env python3
"""Trap 49 check, is the latency you are blaming on the model actually client-side?

Measures client-observed latency for a request, compares it against what the server itself
says the request took, and reports the unexplained gap. A large, roughly CONSTANT, client-only
gap is not a model or engine problem, in our case a dead IPv6 route on an mDNS endpoint added
~30s to every request while the server log showed 9.8s of real work.

Also runs the dual-stack resolution check that identifies the cause.

Exit 0 = gap under --max-gap, 1 = unexplained gap, 2 = could not run.

Usage:
  python3 latency_reconciliation.py --base-url http://HOST.local:8080/v1 --model my-model
  # then, to confirm the fix:
  python3 latency_reconciliation.py --base-url http://10.0.0.5:8080/v1  --model my-model
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

PROMPT = "Reply with exactly the word: ok"


def timed_call(base_url, model, timeout):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 8,
        "temperature": 0,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return time.perf_counter() - t0, d


def server_total_seconds(d):
    """Best-effort: several servers report their own timings in the response."""
    for key in ("timings", "timing"):
        t = d.get(key)
        if isinstance(t, dict):
            for k in ("total_ms", "predicted_ms"):
                if k in t:
                    return float(t[k]) / 1000.0
    return None


def dual_stack_report(base_url):
    host = urllib.parse.urlparse(base_url).hostname
    if not host:
        return
    print(f"\n  resolution check for {host}:")
    fams = set()
    try:
        for info in socket.getaddrinfo(host, None):
            fams.add(info[0])
    except socket.gaierror as exc:
        print(f"    getaddrinfo failed: {exc}")
        return
    has4 = socket.AF_INET in fams
    has6 = socket.AF_INET6 in fams
    print(f"    A record: {'yes' if has4 else 'no'}    AAAA record: {'yes' if has6 else 'no'}")
    if not (has4 and has6):
        print("    single-stack, this trap does not apply")
        return
    print("    DUAL-STACK. Timing each family separately:")
    if not shutil.which("curl"):
        print("    (curl not found; run manually: curl -6 -m 10 <url> ; curl -4 -m 10 <url>)")
        return
    url = base_url.rstrip("/") + "/models"
    for flag in ("-6", "-4"):
        t0 = time.perf_counter()
        rc = subprocess.run(
            ["curl", flag, "-s", "-o", "/dev/null", "-m", "10", url],
            capture_output=True,
        ).returncode
        dt = time.perf_counter() - t0
        verdict = "ok" if rc == 0 else f"FAILED (curl exit {rc})"
        print(f"      curl {flag}: {dt:6.2f}s  {verdict}")
    print("    a v6 route that times out while v4 is instant is the cause, pin the IPv4 literal")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("--max-gap", type=float, default=1.0, help="seconds")
    ap.add_argument("--server-total", type=float, default=None,
                    help="seconds, from the server log, if the response carries no timings")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    lat, srv = [], []
    for i in range(a.n):
        try:
            dt, d = timed_call(a.base_url, a.model, a.timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        lat.append(dt)
        s = server_total_seconds(d)
        if s is not None:
            srv.append(s)
        print(f"  call {i+1}: client {dt:6.2f}s" + (f"   server {s:6.2f}s" if s is not None else ""))

    client = sum(lat) / len(lat)
    server = (sum(srv) / len(srv)) if srv else a.server_total

    print(f"\n  client latency (mean)  : {client:6.2f}s")
    if server is None:
        print("  server total           : unknown")
        print("  -> pass --server-total <seconds> from the server's own request log, or read")
        print("     its `total time` line. This comparison IS the check.")
        dual_stack_report(a.base_url)
        return 2

    gap = client - server
    print(f"  server total           : {server:6.2f}s")
    print(f"  unexplained gap        : {gap:6.2f}s")

    spread = max(lat) - min(lat)
    if gap > a.max_gap:
        print(f"\n  FAIL: {gap:.2f}s is client-side. It is not the model, the quant, the KV")
        print("  cache type, the slot count, or CUDA graphs, all of which we ruled out before")
        print(f"  finding this. Gap spread across calls: {spread:.2f}s "
              f"({'constant, smells like a resolution timeout' if spread < 2 else 'variable'}).")
        dual_stack_report(a.base_url)
        return 1

    print("\n  PASS: client and server agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
