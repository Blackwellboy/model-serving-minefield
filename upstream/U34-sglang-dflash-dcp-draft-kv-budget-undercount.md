# U34: DFlash draft-KV budgeting can undercount memory by the DCP replication factor

**Reported by @milesial.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #33912 is merged.

**Primary source.** [SGLang PR #33912](https://github.com/sgl-project/sglang/pull/33912), read on 2026-08-25.

**Symptom.** Memory/capacity planning for a DFlash-family speculative draft can look safe under DCP while the real draft pool consumes more space than the exact geometry calculation reports.

**Mechanism.** The exact draft-geometry path charged one draft row per target token, but under DCP the draft pool spans the widened virtual location space and the draft term is replicated by `dcp_size`. The fallback path already accounted for that factor; the exact path did not. The merged fix multiplies the draft cell cost by the resolved DCP size.

**What we have not done.** We have not reproduced the affected SGLang DCP/DFlash allocation path on Blackwellboy infrastructure.

## If you have this stack

Pin the pre-fix build and compare reported bytes-per-token/cell-size accounting at DCP1 and DCP>1 with the actual draft-pool geometry and allocation. Keep model, draft geometry and target KV shape fixed.

**CONFIRM.** The pre-fix exact-geometry path fails to scale the draft term with DCP while actual allocation/fallback accounting does; the fixed build restores agreement.

**REFUTE.** The pinned pre-fix exact path already applies the DCP replication factor and matches actual allocation.

## Attribution

Reported and fixed upstream by @milesial in SGLang PR #33912. The registry has not independently reproduced the measurement.