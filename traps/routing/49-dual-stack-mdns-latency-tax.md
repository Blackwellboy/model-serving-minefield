# Trap 49: dead IPv6 route on an mDNS endpoint adds a constant ~30 s that is invisible server-side

**Found by TheTom.**

**Status: reproduced here.** Before/after on the same client, same server, same cached prompt; raw
timings held outside the tree and can be produced on request, per the default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo).

**Symptom.** Every request through an agent client takes **30 to 40 s**, including trivial ones,
including turns with a 100% prompt-cache hit. Direct `curl` from a shell to the same endpoint is
fast. The server's own request log shows real compute finishing in 1 to 10 s, proportional to prompt
size. Nothing on the server looks wrong, because nothing on the server *is* wrong.

**Mechanism.** The endpoint was addressed by an mDNS `HOST.local` name that resolves to **both** an
IPv4 and an IPv6 address. The IPv6 route was dead, not refused, *timing out*. The client's HTTP
library (httpx, under an OpenAI-style SDK) does dual-stack "happy eyeballs"-ish resolution and ate a
long timeout on the dead route before falling back to the working address, **on every single
request**, adding a near-constant tax regardless of prompt size or cache state.

**Stacks and builds bitten.** Any client using a `.local`/mDNS hostname as `base_url` where the host
publishes both A and AAAA records and the v6 path is unreachable. Engine- and model-independent , 
the server never sees it. We hit it with a Python OpenAI-SDK-based gateway; raw `curl` did not
reproduce it, which is what made it hard.

**Why this one deserves an entry.** It cost most of a session, and the false trail was entirely made
of *reasonable* hypotheses that were all correctly ruled out and all wrong: KV quant type
(turbo4 vs q8_0, ruled out), parallel slot count / cross-slot cache misses (ruled out, tested
`-np 1` too), CUDA graphs (ruled out by a full rebuild with them off), and quant format
(ruled out by an A/B). Every one of those is a legitimate suspect. None was it.

**The check.** The diagnostic that cracked it, and the one to run first on any unexplained latency:

> **Compare the server's own logged total time against the client-reported latency for the same
> call.** Server said **9.8 s**; client said **40.2 s**. A large, roughly constant, client-only gap
> is not a model or engine problem.

Runnable: [`checks/latency_reconciliation.py`](../../checks/latency_reconciliation.py).

```
$ python3 checks/latency_reconciliation.py --base-url http://HOST.local:8080/v1 --model $M
  client latency      : 40.21s
  server total (log)  :  9.83s
  unexplained gap     : 30.38s  <-- client-side
  dual-stack check    : A + AAAA records present; curl -6 timed out at 8s, curl -4 ok
  VERDICT: dual-stack resolution tax, pin the IPv4 literal
```

Manual equivalents:

```bash
dscacheutil -q host -a name HOST.local      # macOS: look for both A and AAAA
getent ahosts HOST.local                    # Linux equivalent
curl -6 -m 10 http://HOST.local:8080/v1/models ; echo "v6 exit=$?"
curl -4 -m 10 http://HOST.local:8080/v1/models ; echo "v4 exit=$?"
```

**The fix.** Use a **raw IPv4 literal** as `base_url` for local inference endpoints. Latency went
from 30 to 40 s to **0.9 s** on an otherwise-identical cached request.

Two deployment gotchas after the config change: a supervised gateway needs a restart to pick it up,
and a desktop app that spawns its **own** backend process needs a full quit and relaunch, not a
gateway restart, otherwise you will conclude the fix didn't work.

**Generalization.** Any time a `.local`/mDNS hostname is a `base_url` for a latency-sensitive
service and requests feel slow with no server-side explanation, suspect dual-stack resolution
**before** chasing model or engine config. Prefer raw IPs for local inference endpoints.

**Found.** 2026-07-05, after the decode-speed and MTP work on the same box had already been
completed, those fixes were real and stood on their own, but this was the actual blocker.

**Attribution.** TheTom.
