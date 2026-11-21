# Trap 172: tokens per second from agent wall time per call is not decode speed

**Found by Blackwellboy.**

**Status: measured here, raw not published.** One first-party lane; the
per-call log is not published. The check separates the two numbers on any
lane in a handful of requests.

**Symptom.** An agent framework or gateway log says the model runs at about
57 tok/s at long context, down from about 80 at short context. It looks like a
long-context decode slowdown, and you start tuning attention kernels or KV
settings.

**Mechanism.** The agent's per-call figure is output tokens divided by the
wall time of the whole call, which includes prefill of the new part of the
prompt, queueing, tool round trips the framework counts inside the call, and
streaming overhead. At 150K to 190K tokens of context even a mostly cached
prompt has real prefill work on every turn, so the per-call figure falls while
decode itself has not moved.

**Stacks and builds bitten.** 2x DGX Spark (GB10), TensorFold TP=2, a
DeepSeek-V4.1-Flash EXL3 checkpoint, driven by an agent framework at 150K to
190K context, 2026-10-22. The framework reported about 57 tok/s; the engine's
decode rate over the same calls was flat at about 79 to 83 tok/s.

**The check.** For a few real calls, log the engine-side prefill time, decode
time and token counts, or measure a prefill floor yourself (the same prompt
with `max_tokens=1`, non-streaming, three times). Decode rate is
`(completion_tokens - 1) / (total_seconds - prefill_floor_seconds)`. Confirmed
when that decode rate is flat across context depth while the per-call figure
falls.

**The fix.** Report prefill, decode and end-to-end per-call throughput as
three separate numbers, each named. Tune prefill (prefix-cache hit rate, chunk
size) when per-call time is the complaint and decode is flat.

**Found.** 2026-10-22, chasing a reported long-context slowdown on a
production agent lane.

**Attribution.** Blackwellboy.

**Related.** [80](../runtime/80-reasoning-parser-batches-sse-deltas.md),
[135](135-concurrent-http-clients-are-not-concurrent-model-execution.md),
[60](../runtime/60-cold-prefill-and-cache-hit-disagree.md).
