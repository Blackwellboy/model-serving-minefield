# Trap 128: an admission flag the scheduler never reads starves decode while the preemption counter sits at zero

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Root mechanism
documented upstream by the Anemll DSpark recipe maintainers for the exact
image class the finder runs; the finder observed the same degradation shape
on a private 2x DGX Spark (GB10) lane on 2026-08-13 and confirmed the often
queued fix flag is a no-op on this build. Blackwellboy has not independently
reproduced this lane. Counts and conditions below; raw logs are private.

**Symptom.** Under two or more concurrent requests that are all still
prefilling, decode collapses: worst inter-token latency climbs by an order of
magnitude and throughput falls, growing worse as prompts lengthen. The
preemption counter stays pinned at zero the whole time and the KV pool has
headroom, so the two usual suspects are cleared at once. A single-flag "fix"
you queued produces zero change, which you read as a refuted hypothesis. Both
observations are the trap: a flag the scheduler never reads, and a counter
that by construction cannot see the starvation.

**Mechanism.** In the v1 scheduler on the measured build,
`SchedulerConfig.max_num_partial_prefills` (default 1) is defined but never
read in the waiting-admission loop; only `max_num_seqs` and the token budget
gate new admissions. Several admitted-but-still-prefilling requests each take
up to `max_num_batched_tokens` per step, and decode-active requests further
down the running list receive `num_new_tokens == 0` and are skipped with
`continue`, not preempted. Because nothing is preempted, the preemption
counter cannot move, and the starvation is invisible to the counter that
normally reports it. The corresponding CLI flag is accepted but has no effect
on this build, so the obvious fix changes nothing and reads as a negative
result.

**Stacks and builds bitten.** vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), tensor parallel 2, two DGX Spark
(GB10) nodes, stock DeepSeek-V4-Flash-0731, DSpark speculative decoding,
`--max-num-seqs 4`, `--max-num-batched-tokens 8192`, chunked prefill on.
Upstream before/after on this image class with 8 cold lanes (published by the
recipe maintainers): at an 8K prompt wave worst tok/s went 2.07 to 15.31 and
worst inter-token latency 482 ms to 65 ms; at 16K 0.47 to 14.86, 2123 ms to
67 ms; at 32K 0.36 to 14.80, 2790 ms to 67.6 ms. The mechanism needs two or
more concurrent prefills, not `max_num_seqs = 8`, so the finder's
`--max-num-seqs 4` lane still qualifies; the finder's own degradation
measurements (severe slowdown growing with prompt length, `num_preemptions`
pinned at zero) matched the upstream description.

**The check.** Under load with concurrent prefills and rising inter-token
latency, do not clear the scheduler on the preemption counter. Read the
scheduler's waiting-admission loop and grep for reads of
`max_num_partial_prefills`. If the value is defined and never consumed, this
is the trap. Confirm the single-variable experiment would be a false
negative: apply the flag change and expect zero effect because nothing reads
it.

**The fix.** Land the scheduler hotfix that makes the flag mean something.
Keep `max_num_partial_prefills` at its default of 1; raising it recreates the
starvation the fix removes. Cap how much of a single prefill lands in one
step with the long-prefill token threshold the hotfix pair expects (e.g.
1024), not a value at or above the batch budget, which caps nothing.

**Found.** 2026-08-13, while staging the recipe's scheduler fixes; the finder
had `--max-num-partial-prefills 2` queued and verified on the image that the
flag is a no-op.

**Attribution.** @sethforprivacy. Upstream: Anemll DSpark recipe issue #27 and
its fix; the finder's own observation of the degradation and the inert flag
on the live lane.

**Related.** [41](41-static-batching-buys-power-not-throughput.md), [106](../memory/106-kv-occupancy-ceiling-is-not-a-leak.md), [36](../evaluation/36-token-cap-is-an-arm-level-handicap.md), [77](../reasoning/77-only-one-request-field-is-validated.md).
