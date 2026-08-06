# Trap 11: speculative depth has a sharp peak, and a smart search misses it

**Found by Blackwellboy and TheTom.**

**Status: reproduced here** (20-cell exhaustive grid, published raw); the search-strategy hazard is visible in a public tuning tool.

**Symptom.** "The model is slow" after someone raised the speculative depth
to be safe. Or a tuner reports an optimal config that is measurably worse
than a hand-picked one. Throughput versus draft depth K is assumed smooth
and monotonic, and it is neither.

**Mechanism.** Draft acceptance collapses past the drafter's effective
depth. On our stack, per-position acceptance went to roughly zero past
position 3 with a DFlash drafter, so K=7 peaked at every concurrency level
and **K=8 and above collapsed throughput at every seqs level**, with TTFT
degrading ~50 ms too. A higher K silently converts speculation from a win
into pure overhead.

The search hazard follows: a binary or greedy search over K assumes a
unimodal, smooth response. A cliff right past the peak means the search can
straddle it and settle somewhere flat and wrong.
[mrpmorris/sparkrun-recipes](https://github.com/mrpmorris/sparkrun-recipes)'
`optimise.py` searches `num_speculative_tokens` over (1, 24) "by binary
splitting" per its own docs, which is exactly the strategy shape that can
miss a K=7 peak with a K=8 cliff. (His tool also caps MTP drafters to a
narrower range for the head-count reason, which is the right instinct.)

Corroborating workload angle, credit TheTom: the same DFlash drafter on
llama.cpp measures **53.8% acceptance and 1.15x decode on real code editing
versus 0 to 8% acceptance and 2.1x SLOWER on synthetic filler text**
([guide, sampling and serving](https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md)).
Benchmark speculation on filler and you will wrongly conclude the drafter is
broken; deploy at too-deep K and you will wrongly conclude the model is
slow.

**Stacks and builds bitten.** vLLM + DFlash on DGX Spark GB10 (our 20-cell
grid, raw per-cell JSON published:
[sweep](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/sweep));
llama.cpp + DFlash on the same model family (TheTom's workload split).

**The check.** Sweep K exhaustively in a window around the drafter's head
count, on your real workload mix, one full restart per cell. Do not
extrapolate between K values and do not tune speculation on synthetic text.

**The fix.** Pin the measured peak (K=7 for this drafter on this stack) and
treat any K change as a re-measurement, not a config tweak.

**Found.** 2026-07-23 (grid), workload split published in TheTom's guide.

**Attribution.** Blackwellboy (grid); TheTom (workload sensitivity);
@mrpmorris's tool cited for the search-shape hazard, not as a measured miss.
