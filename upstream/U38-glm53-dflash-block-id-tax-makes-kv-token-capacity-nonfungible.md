# U38: a logged KV-token pool can overstate resident-session capacity when draft layers consume unique block IDs

**Reported by @MiaAI-Lab.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer reproduced.** MiaAI-Lab measured the block-ID tax on its 2x GB10 serve, implemented padded slot-sharing, and published before/after occupancy plus long-session receipts.

**Issue state: closed, fixed.** Issue #13 was closed and PR #14 was merged.

**Primary source.** [MiaAI-Lab issue #13](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/13) and merged [PR #14](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/pull/14), read on 2026-08-30.

**Symptom.** The GLM-5.3 DFlash2 recipe logged roughly 1.1 million GPU KV tokens, yet a single ~36K request consumed 44.6% of the pool and three ~256K sessions could not be resident. Lowering `max-model-len` did not convert the apparently spare token headline into proportional extra long-session capacity.

**Mechanism.** Five DFlash2 sliding-window layers used standalone tensors with globally unique BlockPool IDs. Compacting the draft manager block removed a per-block byte blow-up but did not remove the ID tax. The hybrid Mamba plus DFlash window demand therefore carried a large length-independent floor that a single global "KV tokens" headline did not express. The merged fix padded slot-shares each draft layer onto an MLA tensor at window-bounded IDs, preserving target `fp8_ds_mla` while changing allocator geometry rather than model quality.

The maintainer's published before/after moved the logged pool from 1,096,153 to 1,754,237 tokens, one ~36K request from 44.6% to about 16% KV, and allowed three concurrent requests in the reported occupancy tests. PR #14 explicitly warns that the 1.75M figure is hybrid BlockPool accounting, not 1.75M interchangeable tokens of one uniform tensor layout.

**What we have not done.** We have not independently reproduced the original capacity failure or the padded slot-share fix on Blackwellboy infrastructure. The claim is scoped to this grouped GLM/DFlash cache geometry.

## If you have this stack

On the affected recipe, record global logged KV tokens, total block IDs, per-cache-group page geometry and one-request occupancy for a small/medium long prompt. Attempt the claimed resident-session count. Repeat after the merged slot-share fix with the same model/runtime/utilization and record both the global headline and actual per-request occupancy.

**CONFIRM.** The pre-fix build shows standalone draft groups consuming unique BlockPool IDs so real resident-session capacity is far below naive division of the global KV-token headline, while the slot-share fix reduces block-ID/occupancy cost and admits the previously failing session set.

**REFUTE.** Per-group IDs are already shared on the alleged affected revision, actual resident capacity matches the global token arithmetic, or the same capacity failure persists with the fixed allocator geometry proven active.

## Attribution

Reported, measured and fixed by MiaAI-Lab in issue #13 / merged PR #14. The registry has not independently reproduced the measurement.
