# Trap 157: n-gram speculation can win single-stream and lose at real concurrency

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #174](https://github.com/Blackwellboy/model-serving-minefield/issues/174)).

**Symptom.** An n-gram speculative configuration looks faster in a standard single-stream decode test but becomes materially slower per stream when the server handles its real concurrent load.

**Mechanism.** On vLLM 0.28.0 the measured n-gram path logs that async scheduling is unsupported and will be disabled. The speculative arm therefore changes both decoding and scheduling. On the reported two-request lane, single-stream headline throughput improved while two-stream per-request throughput fell substantially.

**Stacks and builds bitten.** vLLM 0.28.0, Gemma-4-26B-A4B-NVFP4, n-gram k5 lookup 1-3, `max_num_seqs=2`, DGX Spark GB10.

**The check.** Benchmark matched speculation-on/off arms at the production concurrency, record batch wall/completed-work throughput and per-stream rates, and preserve the startup line showing whether async scheduling was disabled.

**The fix.** Choose speculative settings from the target concurrency rather than a single-stream benchmark. If the scheduling change makes the production lane slower, remove the speculative config.

**Found.** 2026-10, vLLM concurrency qualification.

**Attribution.** @scottleimroth.
