# Trap 115: exit status 137 is not OOM-killer proof

**Found by Blackwellboy** (distributed model-load failure adjudication).

**Status: contributor-measured, conditions as reported.** Observed during
rank-local CUDA load failure analysis on multi-node serving bring-up;
sanitized. Mechanism is general to Linux process status interpretation.

**Symptom.** A process exits with status **137**. Logs or chat summaries
say "OOM killed" or "the kernel OOM killer took it." Follow-up work chases
cgroup limits and memory pressure while the only hard facts may be:

1. an allocation API returned failure (for example CUDA `cudaMalloc`), and/or
2. the process exited with 137.

No `dmesg` / journal OOM killer line, no cgroup OOM event, no killer
attribution for that PID/time window is present.

**Mechanism.** On Linux, exit status **137 = 128 + 9** means the process
received **SIGKILL**. That is a signal-delivery fact, not a cause fact.
SIGKILL can come from:

- the kernel OOM killer,
- an operator or orchestrator `kill -9`,
- a watchdog, job scheduler, or container runtime,
- other policy agents,

and exit 137 alone does not name which.

Separately, an allocator failure (for example device allocation failure)
can be **true and measured** while OOM-killer attribution remains
**unproven**. Collapsing those three claims:

1. allocation failed,
2. process exited 137,
3. OOM killer killed it,

into one sentence invents a root cause the evidence does not support.

**What the tempting diagnosis gets wrong.**

- Treating 137 as synonymous with "OOM".
- Treating allocator failure as proof of OOM-killer.
- Treating absence of OOM-killer logs as proof it was not OOM (also invalid
  without a complete log search).

**Stacks and builds bitten.** Any Linux-hosted load/serve path where exit
codes are read from shells, orchestrators, or CI wrappers. Especially
common when CUDA/host allocation fails and a wrapper then dies with 137.

**The check.** Before writing "OOM killed":

1. Record the **exit status** and any **allocator error** strings separately.
2. Search kernel/journal/cgroup logs for OOM killer / memory.oom.group events
   in the same PID and time window.
3. If those are absent, leave OOM-killer as **UNKNOWN_UNADJUDICATED** (or
   equivalent) and do **not** promote it to a confirmed cause.
4. Do not convert unresolved infrastructure death into a model-quality
   negative without an explicit policy.

Evidence Packet / failure-cause discipline: keep
[`docs/failure-cause-taxonomy.md`](../../docs/failure-cause-taxonomy.md)
and evaluation `CLIENT_TIMEOUT` / `HARNESS_ERROR` / `UNKNOWN_UNADJUDICATED`
style separation; do not invent a cause to avoid UNKNOWN.

**The fix.** Adjudication language:

- "process exited 137 (SIGKILL)" when only the status is known,
- "allocation failed: ..." when the allocator said so,
- "OOM killer attributed: ..." only with kernel/cgroup evidence.

**Claim boundary.**

- May claim: 137 proves SIGKILL-class termination, not OOM-killer identity.
- Must not claim: 137 can never be OOM; this trap diagnoses a specific
  historical PID without its logs.

**Found.** 2026-08 distributed load failure adjudication (sanitized).

**Attribution.** Blackwellboy (measurement and adjudication discipline).

**Related.** Memory pressure and UMA traps ([13](../memory/13-utilization-fraction-on-unified-memory.md),
[98](../runtime/98-speculative-decode-default-max-seqs-oom-uma.md)) discuss
real memory limits; they do not license 137→OOM-killer equivalence.
[16](16-finish-reason-is-not-a-failure-signal.md) is the same shape of field
misread in a different domain.
