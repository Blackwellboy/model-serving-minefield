# Trap 133: a DSpark draft loader can silently drop shared-expert weights and halve speculative yield

**Found by @tonyd2wild.**

**Status: contributor-measured, conditions as reported.** @tonyd2wild measured the before/after lane and documented the source mapping in [issue #38](https://github.com/Blackwellboy/model-serving-minefield/issues/38). Blackwellboy has not independently reproduced the performance rows. The source locations and missing mapping are inspectable; the contributor's raw per-request benchmark rows are not published.

**Symptom.** The model is coherent and correct, the server reports no warning at normal log level, and speculative decoding is clearly active -- but acceptance and decode throughput sit around half of the expected lane. The target verifier hides the drafter defect because every bad proposal is simply rejected.

On the reported lane, repairing the loader moved cumulative acceptance **25.7% -> 60.2%**, accepted tokens per step **2.28 -> 4.01**, and mean decode throughput **32.7 -> 55.4 tok/s**, while decode steps/s stayed roughly flat (**14.4 -> 13.8**). A warm peak-finder on the fixed path reached **78.4 tok/s at 98.9% acceptance**. The only load-time trace was twelve debug-level `Skipping unknown DSpark weight` messages.

**Mechanism.** The draft loader's `_STACKED_PARAM_NAME_MAPPING` omitted the two shared-expert rows for `.shared_experts.w1` and `.shared_experts.w3`. Across three draft stages that silently dropped twelve tensors belonging to the always-on shared expert. The target model's loader already had the equivalent mapping; the draft path did not. Because the target verifies every emitted token, output quality can stay green while speculative acceptance collapses.

This is a sibling of [Trap 109](../quantization/109-requant-skips-draft-layer-experts.md), not a duplicate. Trap 109 is a checkpoint/requant problem that leaves draft experts in the wrong representation. This entry is a **serving-loader name-mapping gap** on an otherwise loadable drafter path.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3`, private fork with custom sm_120/sm_121 kernels; `deepseek-ai/DeepSeek-V4-Flash-0731` plus a community-abliterated derivative on the second lane; FP8 target weights, NVFP4 MLA KV, DSpark draft stages; two DGX Spark GB10 nodes, TP=2 over RoCE; `dspark_block_size: 5`, target layer ids 40/41/42, markov rank 256, probabilistic draft sampling, prefix caching and chunked prefill enabled.

**The check.** Compare the target loader's stacked-parameter mapping with the DSpark draft loader's mapping on the exact installed build. The affected draft path is missing the shared-expert `w1` and `w3` rows. Then enable debug logging for one load and look for unknown DSpark-weight skips. Finally scrape the server's speculative counters under a fixed workload; a clean target with abnormally low accepted tokens per step is the signature this bug can hide behind.

Do not estimate decode tok/s from SSE chunk count on this stack: one streamed chunk can contain all tokens accepted in one speculative step. Use completion-token accounting against wall time, and keep steps/s separate from tokens/s.

**The fix.** Use a build whose DSpark draft loader carries the shared-expert mapping, or add the two missing mapping rows to the pinned loader and verify that the unknown-weight skips disappear. Make skipped DSpark weights a launch gate or at least a warning; a debug-only skip is too quiet for tensors that can halve the drafter's useful work.

**Found.** 2026-08-15, after low speculative acceptance was traced back from metrics to twelve debug-only skipped weights.

**Attribution.** @tonyd2wild found and measured the loader gap and filed [issue #38](https://github.com/Blackwellboy/model-serving-minefield/issues/38). Keep the performance figures labelled contributor-measured; the source mapping is independently inspectable on the affected build.

**Related.** [109](../quantization/109-requant-skips-draft-layer-experts.md), [71](71-mtp-config-key-and-draft-count.md), [62](62-spec-decode-garble-under-wrong-drafter-config.md), [80](80-reasoning-parser-batches-sse-deltas.md).
