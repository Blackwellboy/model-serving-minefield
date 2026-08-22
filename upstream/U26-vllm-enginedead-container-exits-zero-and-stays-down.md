# U26: an engine death can exit the serving container with code 0 and defeat restart-on-failure

**Reported by @DaveCharland; operational fix integrated by @tonyd2wild.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The source maintainer agreed the zero-exit behavior was an operational bug and merged `restart: unless-stopped` into the recipe.

**Issue state: closed, fixed.** The recipe-side restart-policy mitigation is merged in PR #23; the original low-level CUBLAS trigger remains a separate unresolved investigation.

**Primary source.** [issue #8](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/issues/8) and [merged PR #23](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/23), read on 2026-08-21.

**Symptom.** A distributed vLLM endpoint dies under traffic and remains unavailable until a human restarts it, yet Docker reports the serving containers as `Exited (0)` rather than failed. A restart policy keyed only to non-zero failure therefore does nothing.

The public incident shows a rank-0 CUDA/CUBLAS fault followed by `EngineDeadError`, an HTTP 500, orderly API-server shutdown, and a later NCCL timeout on the surviving rank. Docker recorded both containers as exited with code 0 and `OOMKilled=false`. Manual restart restored service.

**Mechanism.** The primary engine fault is not the mechanism of this entry. The operational trap is the **failure-to-process-status translation**: the inner engine has already died, but the outer API/container lifecycle completes as a clean exit. Infrastructure that interprets exit code 0 as success cannot distinguish a deliberate shutdown from an engine-death outage and therefore may not restart the service.

The source recipe mitigates this with `restart: unless-stopped`, which restarts a container that exits regardless of zero/non-zero status unless the operator intentionally stopped it. The source discussion separately argues that propagating a non-zero fatal exit from EngineDead would be the cleaner runtime-level behavior.

**What we have not done.** We have not reproduced the engine-death/exit-code sequence on our own vLLM lane. We also do not adopt the issue thread's competing hypotheses for the original CUBLAS fault; those remain mining material rather than this entry's cause.

## If you have this stack

On a disposable service, capture the API-server PID, engine PID, container restart policy and exit status. Induce or replay a known fatal engine failure without manually stopping the container. Record whether the API process shuts down cleanly, what Docker reports as the exit code, and whether `on-failure` versus `unless-stopped` actually restarts it.

**CONFIRM.** A fatal inner-engine failure tears down the endpoint while the container exits 0, so non-zero-only restart logic leaves it down; a policy that restarts zero exits restores the service automatically.

**REFUTE.** The pinned runtime propagates engine death as a non-zero container exit, or the deployed supervisor restarts the service independently of process exit status so the zero-code translation cannot create an outage.

## Attribution

Production-grade failure capture by @DaveCharland in issue #8; operational mitigation reviewed and merged by @tonyd2wild in PR #23. The registry has not independently reproduced it.
