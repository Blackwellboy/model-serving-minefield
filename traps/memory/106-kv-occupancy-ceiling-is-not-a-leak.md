# Trap 106: KV cache occupancy climbing to a ceiling and staying there is not a leak

**Found by Blackwellboy.**

**Status: measured here, raw not published.** 2026-07-28, a 2,400-request
soak across 40 fixed request-count windows on a community abliterated
DeepSeek-V4-Flash checkpoint, vLLM `0.21.1rc1.dev339+g1967a5627bc3`, tensor
parallel 2 across two DGX Spark GB10 nodes, prefix caching enabled. The
per-window counter snapshots are not published; the check below reproduces the
reasoning from two counters on any lane.

**The cause here was our own instrumentation, not the serve.** That is stated
up front because it is the entire reason the entry is worth reading: we built
the curve that looked like a leak, and we nearly reported it as one.

**Symptom.** You watch `vllm:kv_cache_usage_perc` on a healthy lane and it
climbs, monotonically, and does not come back down. Ours went

```
65.1% -> 68.6% -> 72.2% -> 75.8% -> 79.5% -> 82.7% -> 86.0% -> 89.3% -> 92.6% -> 95.8%
```

over the first twelve windows: a near-perfectly linear **+3.6 points per 60
requests**, with no plateau in sight. Extrapolate and it hits 100% within the
hour. Every instinct says memory leak, says page the on-call, says restart the
lane before it wedges.

It is not a leak. Over the following **28 windows it sat at 96.4% and did not
move**, with **zero preemptions for the entire 10.2-hour run** and every one of
2,400 requests returning 200. The lane was never in trouble at any point on
that curve.

**Mechanism.** With prefix caching enabled, KV blocks are retained after a
request completes so a later request sharing that prefix can reuse them. They
are not freed at end-of-request; they are freed by **eviction**, when the cache
needs the space. So occupancy under prefix caching is not "memory in use by
running work" - it is "memory in use by running work, plus everything retained
on the chance it gets reused". A cache that is doing its job **fills up**. An
LRU cache sitting at 96% is a cache with a full working set, which is the
normal steady state, not a fault.

What made ours climb so cleanly is worth naming, because it is a
self-inflicted wound others will inflict on themselves the same way. We issued
a **unique `cache_salt` on every request** in order to force a cold prefill and
get an honest time-to-first-token. A unique salt means no request can ever
reuse another's blocks, so every single request allocated fresh prefix blocks
that were guaranteed dead on arrival. We converted the prefix cache into a
write-only buffer and then watched it fill at a constant rate, which is exactly
what it should do under that abuse.

**The distinction that matters operationally:** occupancy tells you how full
the cache is. It does not tell you whether the engine is struggling. The signal
for struggling is **preemption** - requests evicted from the running batch and
restarted because there was not enough KV to keep them going. Preemptions stayed
at **0** through the entire climb, through the ceiling, and through 28 windows
pinned at 96.4%. A cache at 96% with zero preemptions is fine. A cache at 60%
with rising preemptions is not.

**Stacks and builds bitten.** Observed on a community abliterated
DeepSeek-V4-Flash (`dsv4_ablit_mida`, NVFP4, KV dtype `nvfp4_ds_mla`, block
size 256, 20,139 GPU blocks, `--max-num-seqs 4`, `--enable-prefix-caching`)
under vLLM `0.21.1rc1.dev339+g1967a5627bc3`, tensor parallel 2 on two GB10
nodes. **The behaviour is a property of prefix caching plus LRU eviction, not
of this checkpoint** - expect the same curve on any vLLM serve with prefix
caching on and low prefix reuse, and a faster climb the more unique your
prompts are.

**The check.** Do not alert on occupancy. Decide with two counters plus the
shape of the curve:

```bash
curl -s localhost:8000/metrics | awk '
  /^vllm:kv_cache_usage_perc/ {kv=$2}
  /^vllm:num_preemptions_total/ {p+=$2}
  /^vllm:num_requests_waiting/ {w=$2}
  END {printf "kv=%.3f preemptions=%d waiting=%d\n", kv, p, w}'
```

Sample it on a fixed **request-count** interval, not a time interval, and read
it as:

| occupancy | preemptions rising | verdict |
|---|---|---|
| climbing | no | cache filling. Normal. Wait for the plateau. |
| **plateaued** | **no** | **steady state. This is health, at any percentage.** |
| any | **yes** | real pressure. Act on this, not on the percentage. |
| climbing | no, but never plateaus and requests slow | investigate; you may genuinely be leaking |

**The single question that separates a leak from a full cache: does it
plateau, and do preemptions stay at zero?** A leak does not plateau. A cache
does, at whatever level eviction balances allocation. Ours plateaued at 96.4%
and held for 28 consecutive windows.

If you want the plateau to arrive sooner so you can see it, stop forcing cache
misses: drop any per-request `cache_salt`, or run traffic with realistic shared
prefixes. If you are using a unique salt deliberately (for honest cold TTFT, as
we were), **say so next to any occupancy figure you publish**, because your
curve is an artifact of that choice and does not describe the lane under normal
traffic.

**The fix.**

- Alert on `vllm:num_preemptions_total` increasing and on
  `vllm:num_requests_waiting` staying above zero. Do not alert on
  `vllm:kv_cache_usage_perc` crossing a threshold; there is no threshold that
  means anything on its own.
- If you want a dashboard line for occupancy, label it "cache fill", not
  "memory pressure", so nobody pages on it.
- Record whether your traffic generator forces cache misses. A unique
  `cache_salt` per request, randomised prompts, or a high-cardinality prompt
  prefix will all produce this curve.
- When you do see a monotone climb, hold before declaring: sample across enough
  fixed request-count windows to see whether it plateaus. We nearly filed this
  as a burn at two data points and were wrong; the ceiling behaviour is what
  settled it.

**Found.** 2026-07-28, during a 10.2-hour background-load soak, where the climb
was flagged as "watching, not reporting" at two data points precisely because
two points are not a trend, and resolved only when the curve pinned at 96.4%
with preemptions still at zero.

## Confirming reuse was off, rather than inferring it

The salt explanation above is a mechanism, and a mechanism you have not measured
is a hypothesis. Two counters settle it directly, read immediately before and
after a request:

```bash
curl -s localhost:8000/metrics | awk '
  /^vllm:prefix_cache_hits_total/ {h=$2}
  /^vllm:prefix_cache_queries_total/ {q=$2}
  END {printf "hit fraction: %.4f\n", (q>0 ? h/q : 0)}'
```

On the cross-model arms run from this same harness, every cold request reported a
hit fraction of **exactly 0.0000**. That is the measurement proving no reuse was
occurring, rather than an inference from the fact that we set a salt. Run it once
before you attribute an occupancy curve to your own request construction, because
the alternative explanation, that the stack silently disabled prefix caching for
you, produces the identical curve and is
[trap 47](../runtime/47-prefix-caching-autodisabled-hybrid.md).

**Attribution.** Blackwellboy. Related:
[trap 13](13-utilization-fraction-on-unified-memory.md) on memory fractions
meaning something different on unified memory,
[trap 81](81-stopped-container-has-not-released-memory.md) on memory that looks
held and is not,
[trap 47](../runtime/47-prefix-caching-autodisabled-hybrid.md) on the stack
turning reuse off without being asked, and
[trap 107](107-soak-duration-changes-the-verdict.md), which is the same
"monotone so far is not a shape" error in the other direction: there the series
plateaued and then fully reverted, here it plateaued and stayed.
