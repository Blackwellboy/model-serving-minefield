# U13: `--cache-reuse` is on, but the full prefix state does not exist

**Reported by @ghnp5.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** llama.cpp maintainer @ggerganov explained the iSWA requirement and the reporter confirmed the workaround changed the observed behavior.

**Issue state: closed, resolved as usage.** The issue was closed after `--swa-full` restored cache reuse for the reporter's iSWA case; this was a configuration/state-retention requirement, not a general cache-reuse code fix.

**Primary source.** [ggml-org/llama.cpp issue #15082](https://github.com/ggml-org/llama.cpp/issues/15082), including @ggerganov's iSWA explanation and the reporter's follow-up, read on 2026-08-14.

**Symptom.** `llama-server` launches with `--cache-reuse 1`, repeated chat requests share a large prefix, and the server still reprocesses far more of the prompt than expected. The command line looks right, so the first diagnosis is that prefix caching regressed.

**Mechanism, as stated upstream.** On iSWA models the reuse operation needs the full KV state, not only the sliding-window state. Maintainer guidance states that these models require `--swa-full` for cache reuse because otherwise the state needed to reuse the older prefix has already been discarded. Retaining it uses more memory.

The thread also records an extra reasoning-model caveat: reasoning from response N may not be present in request N+1. If the omitted thinking plus generated region exceeds the available batch/SWA window, reprocessing can still occur. `--cache-reuse` reduces that cost; it does not turn a changed history into an identical prefix.

**Why this is worth an entry.** A launch flag is not runtime evidence. Seeing `--cache-reuse` in `ps` or a wrapper config proves the feature was requested, not that the model's attention/KV policy retained the state required to exercise it. The check is actual reused-prefix/prefill work under the model's real cache mode.

**What we have not done.** We have not run the affected llama.cpp revisions or this iSWA model. We have not measured the memory/throughput tradeoff of `--swa-full` on our hardware.

## If you have this stack

Run an iSWA model with a long stable prefix and two otherwise matched llama-server configurations: `--cache-reuse 1` alone, then the same command plus `--swa-full`. Send repeated requests whose shared prefix is long enough that a full re-prefill is obvious in timing/server metrics.

**CONFIRM.** The cache-reuse-only arm reprocesses the prefix while the `--swa-full` arm substantially restores prefix reuse, at the expected extra memory cost.

**REFUTE.** Both arms retain/reuse the same prefix state on the same llama.cpp revision and model. Record the model's attention type and exact revision because a non-iSWA model does not test this entry.

## Attribution

Reported by @ghnp5. iSWA/full-KV mechanism explained by llama.cpp maintainer @ggerganov; the reporter confirmed `--swa-full` resolved the primary case.
