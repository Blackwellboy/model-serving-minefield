# Trap 129: prefix-cache hits collapse past the sliding-window horizon because the shared hit is the minimum across KV cache groups

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Mechanism documented
upstream by the Anemll DSpark recipe maintainers (issue #26) for the image
class the finder runs; the finder measured the masking effect on a private 2x
DGX Spark (GB10) lane on 2026-08-13. Blackwellboy has not independently
reproduced this lane. Counts and conditions below; raw logs are private.

**Symptom.** Long warm requests suddenly re-prefill at zero cache hits, with
no preemptions and no KV pressure. Your live prefix-cache hit rate is
excellent (97% on daytime traffic), which makes the collapse look impossible,
and it is: the collapse binds on context length, not on load. Above the
sliding-window horizon, warm traffic pays full cold-prefill cost and nobody
can see why from the aggregate counters.

**Mechanism.** The model's KV is stored in several cache groups, one
full-attention (MLA) group and several sliding-window (SWA) groups. The
prefix-cache lookup takes the minimum hit length across groups and reports
that as the common prefix. SWA managers free blocks outside their window by
design, so past the window length their hit length is zero, and the minimum
zeroes the common hit even when the full-attention group still holds the
entire prefix. Warm requests therefore fully re-prefill. The fix has two
parts: a coordinator hotfix and a retention-interval environment variable,
because on the upstream lane the hotfix alone still scored 0/8 correct at
44K+ (dense SWA tails evicted MLA prefix blocks before the answer).

**Stacks and builds bitten.** vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), tensor parallel 2, two DGX Spark
(GB10) nodes, stock DeepSeek-V4-Flash-0731, NVFP4 MLA KV cache
(`nvfp4_ds_mla`), prefix caching on, `--max-num-seqs 4`. Finder's
measurements: 97% live prefix-cache hit rate on daytime traffic at prompt
lengths below the horizon; and a 24 s probe on a busy cluster swept up
721,882 live queries and reported a 95.1% hit rate, so a check that does not
control for context length cannot see the trap either.

**The check.** Do not certify the prefix cache from an aggregate hit rate.
Drive the hit-rate check at context lengths at or above the sliding-window
horizon, with hits split by request length, and compare group-level hit
lengths if the engine exposes them. Then set the retention-interval variable
(on this stack `VLLM_PREFIX_CACHE_RETENTION_INTERVAL`, e.g. 4096), re-measure
at the same above-horizon lengths, and only then judge the fix: the
coordinator hotfix alone produced zero correct results at 44K+ on the
upstream lane.

**The fix.** Land the coordinator hotfix AND set the retention interval so the
full-attention group's blocks outlive the sliding-window eviction. Re-measure
the above-horizon hit rate after both, not after the hotfix alone. On a lane
whose mean prompt sits far below the horizon, treat the excellent aggregate
hit rate as a masking condition, not a clearance.

**Found.** 2026-08-13, while staging the recipe's prefix-cache fixes and
re-checking the live hit-rate measurement.

**Attribution.** @sethforprivacy. Upstream: Anemll DSpark recipe issue #26 and
its fix; the finder's measurement of the masking aggregate hit rate on the
live lane.

**Related.** [25](../template/25-empty-think-blocks-poison-prefix-cache.md), [47](../runtime/47-prefix-caching-autodisabled-hybrid.md), [92](../runtime/92-prompt-cache-is-a-second-divergence-source.md), [60](../runtime/60-cold-prefill-and-cache-hit-disagree.md).
