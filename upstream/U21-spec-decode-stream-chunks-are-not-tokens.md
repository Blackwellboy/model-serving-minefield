# U21: counting streamed chunks as tokens can under-report speculative decode by multiples

**Reported by @tonyd2wild.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The correction is in the source recipe's current main and is repeated by independent contributors using the recipe.

**Issue state: closed, fixed.** The source documentation now tells benchmarkers to use completion-token accounting rather than SSE-delta count.

**Primary source.** [source commit 8a62e8b8](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/commit/8a62e8b8d04e5c65d4b4b9dc60134f5b3547f7c5), read on 2026-08-21; see also the current README's 0731 benchmarking correction.

**Symptom.** A speculative-decoding server looks dramatically slower when throughput is calculated by counting streamed SSE content deltas. The same request measured by real completion-token accounting is several times faster.

The source reports the identical request as roughly 14.7 units/s when stream deltas were treated as tokens versus 60.1 actual tokens/s using completion-token accounting.

**Mechanism.** On the affected vLLM speculative path, the server emits at most one SSE chunk per decode **step**, and that chunk can carry several tokens accepted in the step. A client that increments a token counter once per content delta therefore measures steps/s, not tokens/s. The error grows with mean accepted draft length, so the most successful speculative runs can be the most under-counted.

**What we have not done.** We have not reproduced the 14.7 versus 60.1 pair on our own endpoint. The entry does not claim every streaming implementation batches accepted speculative tokens into one delta; it says the wire shape must be measured before chunk count is used as token count.

## If you have this stack

Send one deterministic request twice under the same warm state: once non-streaming and once streaming. Record wall time, `usage.completion_tokens` where available, server-side `generation_tokens_total`, the number of streamed content deltas, and speculative accepted-tokens-per-step metrics. Do not infer tokens from the number of callbacks.

**CONFIRM.** Stream-delta count tracks decode steps and materially under-counts actual completion tokens, while `completion_tokens / wall` agrees with server token counters.

**REFUTE.** The pinned server emits one token per counted delta for the tested path and chunk-count throughput agrees with independent completion-token accounting within measurement noise.

## Attribution

Documented and measured by @tonyd2wild in the source recipe. The registry has not independently reproduced the measurement.
