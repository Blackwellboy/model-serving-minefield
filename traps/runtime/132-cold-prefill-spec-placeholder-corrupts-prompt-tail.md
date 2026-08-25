# Trap 132: speculative placeholders can corrupt the prompt tail only on cold chunked prefill

**Found by @tonyd2wild; original scheduler-guard root-cause fix credited to @Roady001.**

**Status: contributor-measured, conditions as reported.** @tonyd2wild measured the bad/good arms on a private 2x DGX Spark (GB10) lane and reported them in [issue #36](https://github.com/Blackwellboy/model-serving-minefield/issues/36). Blackwellboy has not independently reproduced that lane; the captured production payload and raw per-request rows are not published.

**Symptom.** A speculative-decoding server passes warm smoke tests and ordinary short prompts, then real agent sessions that force a cold prefill begin their answer by continuing the system prompt. The corruption is coherent enough to look like a model misunderstanding: replies can start mid-word, reproduce text from the tool/skill catalogue, leak a BOS marker, or return only whitespace while billing tokens. The same prompt becomes clean as soon as its long prefix is warm.

The reported separation was stark: **0/19 warm requests bad** versus **44/44 cold requests bad** across four configurations. The contributor forced the cold path by changing a nonce at the *front* of the long system prompt on every request.

**Mechanism.** On the affected scheduler, speculative-placeholder resizing ran for requests that were still in chunked prefill instead of only for decode steps. That attached speculative tokens to the final prompt chunk of a cold resume and corrupted the prompt tail before generation began. A guard that excludes `is_prefill_chunk` requests from the placeholder path removes that state transition.

The controlled fix is the load-bearing evidence: **44/44 cold bad without the guard -> 0/28 bad with the guard**. Lowering speculative depth was a negative control, not a fix: k=3 remained **10/10 bad** without the scheduler guard, while guarded k=3 and guarded k=5 were both **0/10 bad**. The guard also reduced the reported cold-prefill time from roughly 36 s to roughly 12 s on the captured workload, consistent with speculative work no longer being attached to prefill chunks.

**Stacks and builds bitten.** vLLM `0.21.1rc1` plus a custom GB10 kernel overlay; `fraserprice/DeepSeek-V4-Flash-DSpark`; two NVIDIA DGX Spark GB10 nodes, TP=2 over RoCE; `nvfp4_ds_mla` KV, block size 256; DSpark MTP with `num_speculative_tokens=5`, probabilistic draft sampling; `--max-model-len 1000000`, `--max-num-seqs 6`, `--max-num-batched-tokens 8192`, chunked prefill enabled. The deployed image predated the scheduler guard even though the recipe documented the patched scheduler path.

**The check.** Do not test this with a warm prompt. Use a long prompt and put a unique nonce in its first tokens on every request so prefix reuse cannot rescue the run. Capture the raw first output tokens and compare the same pinned workload with the scheduler guard absent and present. On the affected install, a quick source check is:

```bash
docker exec <container> grep -n 'is_prefill_chunk' \
  /PATH/site-packages/vllm/v1/core/sched/scheduler.py
```

The source check is not a substitute for the cold A/B, but it tells you whether the known guard is even present.

**The fix.** Use a build carrying the scheduler guard, or bind-mount the exact guarded scheduler only when that patch is pinned to the image revision. Do **not** lower speculative depth as a substitute: the contributor's k=3 negative control remained corrupted and only threw away decode throughput.

**Found.** 2026-08-15, after a production-shaped agent payload was forced cold on every iteration and the warm-only smoke-test blind spot became reproducible.

**Attribution.** @tonyd2wild measured the warm/cold separation, the guarded A/B, the speculative-depth negative control and the latency change, and filed [issue #36](https://github.com/Blackwellboy/model-serving-minefield/issues/36). The issue explicitly credits @Roady001 for the original scheduler-guard root-cause fix. Preserve both credits.

**Related.** [60](60-cold-prefill-and-cache-hit-disagree.md) is a different cold-versus-cache behavioral divergence whose mechanism remains unresolved; [62](62-spec-decode-garble-under-wrong-drafter-config.md) is drafter-configuration corruption; [28](28-mtp-fails-only-under-concurrency-or-temperature.md) is a different speculative-failure boundary.
