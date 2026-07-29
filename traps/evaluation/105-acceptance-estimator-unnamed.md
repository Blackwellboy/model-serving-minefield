# Trap 105: "acceptance rate" without a named estimator is a number nobody can compare against

**Found by Blackwellboy.**

**Status: measured here, raw not published.** 2026-07-28, a 2,400-request
soak across 40 fixed request-count windows on a community abliterated
DeepSeek-V4-Flash checkpoint, vLLM `0.21.1rc1.dev339+g1967a5627bc3`, tensor
parallel 2 across two DGX Spark GB10 nodes, MTP `dspark` with 3 draft tokens.
The per-request rows are not published, so a stranger cannot check our numbers.
The check below settles it on their own lane from two counters and their own
request log, which is the cheaper route anyway.

**Single serve, no baseline arm. The numbers below describe this build and
nothing else - they are not a comparison, and none of them generalise to stock
DeepSeek-V4.** The trap is the estimator ambiguity, which is portable; the
specific percentages are not.

**Symptom.** You publish a speculative-decoding acceptance rate. Someone else
publishes theirs. The two numbers are not comparable and nothing in either
report says so. Worse, both of your own numbers are defensible: on the same
2,400 requests, the same lane, the same day, we can report

- **72.70%**, token-weighted - `accepted_tokens / draft_tokens` summed over our
  own 2,400 turns, which is the shape
  `vllm:spec_decode_num_accepted_tokens_total / ..._num_draft_tokens_total`
  gives you, or
- **66.39%**, request-weighted - the mean of per-request acceptance, each
  request counting once.

Same data. A **6.31 point** gap. Neither is wrong. Only one of them answers the
question you were actually asked, and reports rarely say which.

**There is a third number, and it is the one that will bite you.** Read straight
off `/metrics` without scoping, the token-weighted figure for the same run is
**73.4%**, because the counters are process-wide and include traffic outside your
request set: in our case a pre-soak baseline and two positive-control requests.
Pairing that process-wide numerator against a request-scoped denominator is not
like-for-like, and it inflated our own published gap from 6.31 to 7.0 points
until it was caught. The endpoint will hand you the unscoped number and call it
acceptance. **Scope it to your own requests before you compare it to anything.**

And a pooled number of either kind can describe **no** actual workload on the
lane. Per task family, n=400 each, interleaved so the mix is constant by
construction:

| family | acceptance (request-weighted) |
|---|---|
| math, thinking off | **78.14%** |
| code generation | 75.74% |
| math, thinking on | 74.80% |
| long-context recall | 66.18% |
| summarisation | 60.10% |
| short chat | **43.37%** |

**A 34.78 point spread**, against a pooled 66.39% that matches none of them.
Quote the pooled figure to someone whose traffic is mostly short chat and you
have overstated their acceptance by 23 points.

**Mechanism.** The two estimators weight differently and the workload mix
decides the gap.

Token-weighting sums accepted and drafted tokens across all requests, so a
single 1,500-token code generation contributes ~37x the weight of a 40-token
chat reply. Because long generations here also have the *highest* acceptance
(75.7% for code vs 43.4% for chat), token-weighting is pulled toward the best
cells. Request-weighting gives every request one vote regardless of length, so
it is pulled toward whatever your traffic has most of.

The consequence is that **the pooled acceptance of a mixed workload is a
property of the mix, not of the model or the speculator.** Change the ratio of
short to long requests and the number moves without anything about the serve
changing. Two labs running identical builds will publish different acceptance
rates if their prompt mixes differ, and both will be right.

Short generations accept worse here for a structural reason worth stating: a
short reply is mostly its first few tokens, and the first tokens of a reply are
the least predictable part of it. Acceptance improves once the model is
committed to a continuation. So "acceptance" measured on chat-length traffic is
close to a worst case, and measured on long code generation is close to a best
case, on the same serve.

**Stacks and builds bitten.** Measured on a community abliterated
DeepSeek-V4-Flash (`dsv4_ablit_mida`, NVFP4, KV dtype `nvfp4_ds_mla`, block
size 256, `--max-num-seqs 4`, `--max-model-len 1048576`) under vLLM
`0.21.1rc1.dev339+g1967a5627bc3` with MTP `dspark`, 3 draft tokens, tensor
parallel 2 on two GB10 nodes. **The estimator ambiguity is not specific to any
of that** - it applies to any serving stack exposing pooled speculative
counters, which is all of them. vLLM's `spec_decode_num_accepted_tokens_total`
/ `spec_decode_num_draft_tokens_total` pair is token-weighted, and that is the
number most people scrape.

**The check.** Compute both estimators on your own lane and report the gap.
Two counters plus your own request log; no model knowledge required.

Token-weighted. **Subtract two snapshots. Do not divide one.**

`vllm:spec_decode_*` are cumulative process-lifetime counters. A single scrape
divided in place gives you the ratio since the server started, not the ratio
over your window, and it silently includes every request anyone else sent. That
is the same unscoped error this entry is about, so the check must not commit it:

```bash
snap() { curl -s localhost:8000/metrics | awk '
  /^vllm:spec_decode_num_accepted_tokens_total/ {a=$2}
  /^vllm:spec_decode_num_draft_tokens_total/ {d=$2}
  END {print a, d}'; }

read A0 D0 < <(snap)      # before your workload
#   ... run your requests ...
read A1 D1 < <(snap)      # after
awk -v a0=$A0 -v d0=$D0 -v a1=$A1 -v d1=$D1   'BEGIN {printf "token-weighted acceptance (this window): %.4f
", (a1-a0)/(d1-d0)}'
```

A one-shot `a/d` is only the window value on a server that has served nothing
else since boot, which is a condition you have to establish rather than assume.
Ours had not: a pre-soak baseline and two positive controls sat inside the
lifetime totals, which is precisely how the 73.4% got quoted.
tokens_per_step = completion_tokens / decode_steps # in [1, K+1]
request_acceptance = (tokens_per_step - 1) / K
```

Then report all three numbers together:

```
token-weighted    : 0.7270       <- scoped to MY requests
unscoped /metrics : 0.734        <- process-wide, do not pair with the above
request-weighted  : 0.6639       <- mean of per-request acceptance
gap               : 6.31 points
per-family        : chat 0.434 (n=400) ... math 0.781 (n=400)
```

**Two assertions that make this check trustworthy, both of which will fire on
somebody's lane:**

1. **Assert `tokens_per_step <= K + 1`.** If it exceeds the ceiling, your
   stream is batching multiple decode steps into one SSE delta and the
   derivation is invalid - see
   [trap 80](../runtime/80-reasoning-parser-batches-sse-deltas.md), where a
   reasoning-parser plugin does exactly that. Ours never exceeded 4.0 across
   2,400 requests, which is what licenses the derivation *here* and is not
   something you may assume *there*.

   **That is necessary and not sufficient, and the gap matters most where the
   answer matters most.** Batching only breaches the ceiling when the batched
   steps were themselves high-acceptance. Batch two *rejected* steps at `K=3`
   and you get one delta carrying 2 tokens: `tokens_per_step` is 2, comfortably
   under 4, the assertion passes, and the derivation reports 1/3 acceptance for
   a pair of steps whose true acceptance was **zero**. Low-acceptance traffic is
   exactly the traffic that hides inside this guard.

   So the ceiling assertion detects the loud case only. Before trusting the
   per-request number, establish independently that the transport preserves one
   engine step per delta: compare `decode_steps` against a server-side step
   count if your stack exposes one, or confirm `tokens_per_step` actually
   reaches `K + 1` somewhere in a high-acceptance sample rather than sitting
   under it uniformly. On a stream that batches, this derivation is not merely
   noisy, it is biased upward on the worst cells.
2. **Attribute the counters.** `vllm:spec_decode_*` is process-wide, so any
   other traffic on the lane is silently inside your number. Difference
   `vllm:request_success_total` against your own request count per window; if
   it is not zero, drafts you did not issue are in your acceptance figure. Do
   not use `http_requests_total` for this - it counts `/health` and `/metrics`
   polls too, which on our lane ran ~44 per window and would have looked like
   large foreign traffic that was not there.

**The fix.** Never publish a bare acceptance rate.

- **Name the estimator, and its scope,** in the same sentence as the number.
  "72.70% token-weighted over our own 2,400 turns" and "66.39% request-weighted"
  are both publishable; a bare "73.4%" is not, and a bare "73.4%" that is
  silently process-wide is worse than not publishing one.
- **Publish per-family with n beside each**, not only a pooled figure. If you
  report one number, report the spread with it.
- **Publish the workload mix**, because pooled acceptance is a property of the
  mix. A number without its mix cannot be reproduced even by you.
- Interleave task families rather than running them in blocks, so drift across
  a long run cannot masquerade as a task effect and vice versa.

## A second serve where the split could not be computed at all

The same week, a 13.009 h soak of NVIDIA Nemotron 3 Super 120B A12B NVFP4
(revision `4f0cf9daaeb7a4d5e23f80a00e7ed15f0e03caf6`, vLLM 0.20.0, single GB10
node, tensor parallel 1, MTP `num_speculative_tokens=3`) produced a clean pooled
acceptance of **64.22% token-weighted across 2,045 turns** and **could not
produce a per-family split at all**.

The reason is a design collision worth stating, because it is easy to build by
accident. Its counters are process-wide, its workload was seven families
round-robin, and its counter scrape fired every 14 turns, which is exactly two
complete cycles. **Every measurement window therefore contained all seven
families in equal counts**, by construction. The design choice that made its
drift result strong, that no family can occupy a contiguous stretch of wall
clock, is the same one that destroyed family attribution. No arithmetic on that
log recovers the split.

That run also shows what the estimator discipline buys you. Its pooled 64.22%
was compared against a previously published 67.33% for the same checkpoint.
**Both are token-weighted**, so the 3.1 point gap is not an estimator artifact
and could not be explained away as one. Mix drift was then bounded at **0.12
points** by measuring per-family completion-token share across run quartiles
(largest swing 0.75 points), so the gap is not a mix effect either. It is
recorded as real, unexplained and not closable from that log, rather than
attributed to a mix difference that was measured and found too small.

**The lesson for instrumentation, before your run rather than after it:** decide
whether you need per-family acceptance *first*. If you do, scrape the counters
immediately before and after each request so the delta is request-scoped, or run
families in contiguous blocks. A round-robin workload plus a periodic scrape
whose period is a multiple of the cycle length gives you perfectly balanced
windows and zero attribution, and you will not find out until you try to compute
the split and cannot.

**Found.** 2026-07-28, in a 10.2-hour background-load soak of a production
DeepSeek-V4-Flash lane, where the intent was to measure drift and the
per-family breakdown turned out to matter far more than the drift did (which
was 0.73 points across 2,400 requests, i.e. nothing). The Nemotron Super
counter-example above is from an independent 13.009 h soak the same week.

**Attribution.** Blackwellboy. Related:
[trap 11](../runtime/11-speculative-depth-peak-and-collapse.md) on speculative
depth needing a sweep rather than a point measurement,
[trap 28](../runtime/28-mtp-fails-only-under-concurrency-or-temperature.md) on
acceptance being multi-axis, and
[trap 80](../runtime/80-reasoning-parser-batches-sse-deltas.md), whose
delta-batching breaks the per-request derivation above.
