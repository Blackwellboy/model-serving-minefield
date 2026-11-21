# Trap 169: a speculative-decoding speedup measured on plain greedy decode is not the speedup your workload gets

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Two first-party lanes, the raw
benchmark logs are not published. The check below re-derives the gap on your
own lane in a few minutes, which is the cheaper route anyway.

**Symptom.** A speculative-decoding change (a new drafter, a deeper or adaptive
verify step, a bigger draft budget) lifts the headline decode number by half or
more. You ship it, and the agent, chat or coding workload it was meant for gets
a small fraction of that gain, or none.

**Mechanism.** Speculative decoding is paid for by acceptance, and acceptance
is a property of the text being generated. The usual headline bench is greedy
(temperature 0), short context, thinking off and a predictable prompt, which is
close to the best case for a drafter: low-entropy continuations, no sampling
noise and no long prefix. Real workloads move every one of those levers the
other way, and each class of output (free prose, JSON, tool calls, reasoning
traces) has its own acceptance curve. A change that buys extra accepted tokens
when acceptance is already high can buy nothing on prose, where the draft is
rejected early anyway. The bench number is real; it is just a measurement of a
different workload. [Trap 111](111-greedy-spec-decode-medians-are-a-content-lottery.md)
is the run-to-run version of the same dependence.

**Stacks and builds bitten.**

- RTX 5090 (450 W), a DFlash2 speculative-decoding engine with an unreleased
  adaptive-verification patch, INT8 KV, a Qwen3.8-27B derivative, 2026-11-21.
  Plain greedy decode rose from about 348 to about 542 tok/s (+56%). On a
  per-class workload set the same build gave about 114 tok/s on free prose, 242
  on JSON, 167 on tool calls and 266 on reasoning traces, a gain of 0% to 23%
  per class over the build without the patch. The change was still worth
  shipping; the headline was not the number to quote.
- 2x DGX Spark (GB10), TensorFold TP=2, a DeepSeek-V4.1-Flash EXL3 checkpoint,
  2026-10-21. The benches ran at temperature 0, thinking off and at most 8K
  context. Real agent use ran at temperature 1, thinking on at high effort,
  150K to 196K context and about 95% prefix-cache hits. Draft acceptance was
  78% to 80% on the code bench and about 60% in real use.

**The check.** Before quoting a speculative-decoding gain, run the same A/B
four ways on the same lane and report all four rows, not one:

1. the headline bench as you normally run it;
2. a per-class set (prose, JSON, tool call, reasoning trace), at least 20
   prompts each, at the sampling settings you actually serve;
3. the same set at your real context depth, with prefix caching in the state
   your clients leave it;
4. the engine's own accepted and drafted counters for each class, read from
   `/metrics` or the server log deltas, not from client-side timing.

Confirmed when row 1's gain is well outside the range of rows 2 and 3. Name
the acceptance estimator you used ([trap 105](105-acceptance-estimator-unnamed.md)).

**The fix.** Quote speculative-decoding gains per output class and at served
settings, with the bench regime written next to the number. Keep the greedy
plain-decode bench as a regression gate, not as the claim.

**Found.** 2026-11-21, while qualifying an adaptive-verification build for a
production swap; the 2026-10-21 lane is the earlier case of the same shape.

**Attribution.** Blackwellboy.

**Related.** [111](111-greedy-spec-decode-medians-are-a-content-lottery.md),
[105](105-acceptance-estimator-unnamed.md),
[52](52-speed-measured-on-a-broken-config.md).
