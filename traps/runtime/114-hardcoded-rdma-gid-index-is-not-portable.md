# Trap 114: a hard-coded RDMA GID index is not portable across hosts

**Found by Blackwellboy** (multi-host Spark fabric qualification campaigns).

**Status: contributor-measured, conditions as reported.** Independent multi-host
RoCE campaigns on DGX Spark class fabric; hostnames and addresses scrubbed.
Not a claim about a particular switch model.

**Symptom.** NCCL / RDMA bring-up fails with QP or GID-related errors when
every host is given the same forced `NCCL_IB_GID_INDEX` (or equivalent
hard-coded index). The same multi-host path succeeds when GID selection is
left automatic (or each host is given the index that actually matches its
own GID table). Operators conclude "the fabric is broken" or "NCCL is bad"
and start swapping cables/switch configs that were never the defect.

**Mechanism.** GID tables are **per-host**. The IPv4-mapped (or other) entry
you need for RoCE is not guaranteed to sit at the same numeric index on
every node. A constant that worked on host A can select a wrong/unusable
entry on host B even when:

- link is up,
- the right HCA is selected,
- MTU/fabric path is healthy,
- automatic selection would have succeeded.

The failure is configuration **identity portability**, not proof of dead
RDMA.

**What the tempting diagnosis gets wrong.** Treating a forced-index failure
as:

- switch blackhole,
- bad NIC,
- "NCCL does not work on this fabric",

before comparing `show_gids` / `ibv_devinfo` style tables across hosts and
retrying with automatic selection.

**Stacks and builds bitten.** Multi-host NCCL over RoCE / InfiniBand-style
GIDs when env forces a single index. Observed across independent Spark-class
qualification campaigns (including distributed model transport bring-up).
General to any multi-node path that hard-codes GID index.

**The check.**

1. On **each** rank host, dump the GID table for the HCA you intend to use
   and record which index holds the address family you need.
2. If indices differ, do **not** force one global number without per-host
   mapping.
3. Prefer automatic GID selection for bring-up unless you have a pinned,
   per-host, verified index map checked into the recipe.
4. Confirm success with the same collective on the same hosts after
   switching from forced-fail to auto (or to the correct per-host indices).

Offline triage of changed transport/env paths can use
[`checks/upstream_change_triage.py`](../../checks/upstream_change_triage.py)
as a prioritisation hint only; it does not replace live GID inspection.

**The fix.** Stop shipping one global `NCCL_IB_GID_INDEX` as if it were a
fabric constant. Document per-host tables in the recipe when a pin is
required; default to auto for first bring-up.

**Claim boundary.**

- May claim: hard-coded same index across hosts can false-fail healthy fabric.
- Must not claim: a specific vendor switch is defective; auto is always
  optimal for production; one correct index for all hosts forever.

**Found.** Private multi-host fabric and distributed-serving qualification
receipts, 2026-07-31 and 2026-08-08 campaigns (sanitized).

**Attribution.** Measured in Blackwellboy-operated multi-Spark fabric
campaigns; mechanism class is general.

**Related.** Readiness hierarchy [112](112-process-liveness-is-not-model-readiness.md)
(green lower gate is not full capability). Not the same owner as wrong-HCA
selection or pure cable defects.
