# U16: MTP is fast and coherent at c1, then corrupts output at a concurrency boundary

**Reported by @dkremez.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: none.** The issue has multiple independent user/contributor reports and active mechanism discussion, but no maintainer-confirmed root cause is claimed here.

**Issue state: open.** The upstream issue remains open as of this audit.

**Primary source.** [vllm-project/vllm issue #35288](https://github.com/vllm-project/vllm/issues/35288), read on 2026-08-14, including later reports on different hardware/version combinations.

**Symptom.** MTP speculative decoding works coherently at low concurrency, then at a higher concurrent decode/mixed-batch regime produces garbage, duplicated spans or repetition loops that run to `max_tokens`. Turning MTP off restores coherent output. Reducing concurrency can also remove the corruption.

The original report describes the transition at four or more concurrent requests on its setup. Later reports show that the exact break point is not a universal integer: one contributor found it moved when `max_num_batched_tokens` changed and was easier to trigger with long inputs, while short inputs stayed stable at higher concurrency. Another user on a different GPU and newer vLLM image reported corruption at `--max-num-seqs 4` disappearing at 2.

**Mechanism status: unresolved upstream.** Comments discuss MTP state/indexing, mixed prefill/decode batches, async state updates and hybrid/prefix-cache interactions. One report found first-position acceptance collapsing near the breakpoint while a later conditional position remained high, which is useful localization evidence. None of that is enough for this registry to choose a definitive root cause.

**Why this is worth an entry.** A speculative configuration can pass every c1 quality and throughput check and still be unsafe at the deployed concurrency/context shape. Throughput qualification therefore needs a correctness oracle at the same batching regime. "MTP on is 1.4x faster" is incomplete if the c4 arm is generating plausible-looking corruption or loops.

This is related to [Trap 28](../traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md), an older upstream-sourced canonical entry grandfathered before the separate upstream tier. U16 keeps this newer vLLM/Qwen-family report in the explicit upstream tier rather than silently upgrading it to first-party evidence.

**What we have not done.** We have not run the affected vLLM/Qwen configurations, reproduced the concurrency breakpoint, or isolated the source-level mechanism. We do not claim that every MTP implementation or every vLLM version has this bug.

## If you have this stack

Pin one affected vLLM/model/speculative configuration. Run identical prompts at c1, c2 and increasing concurrency with MTP ON, then repeat the same matrix with MTP OFF. Include both short prompts and the long-input/mixed-prefill regime that is more likely to expose the issue. Save full output, finish reason, speculative acceptance by position where available, and actual batching settings including `max_num_batched_tokens` and `max_num_seqs`.

**CONFIRM.** A bounded concurrency/batch-shape threshold exists where the MTP arm starts producing corruption/repetition while the matched MTP-OFF control remains coherent, and lowering concurrency or changing the implicated batch shape removes the failure.

**REFUTE.** The pinned allegedly affected build remains quality-identical to the non-MTP control across the reported concurrency/context regime. Report acceptance statistics and exact vLLM revision so a newer fix is not mistaken for failure to reproduce an older build.

## Attribution

Reported by @dkremez in vLLM #35288. Additional public data points in the thread include @bwinken, @vektorprime, @PavelPaha and @marzukia; their proposed mechanisms remain attributed to them rather than adopted as Minefield first-party findings.
