# U24: stale DSpark draft-KV slot ids can kill the engine when a batch condenses

**Reported by @paulbrav.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The source maintainer merged the protective slot guard in PR #4.

**Issue state: closed, fixed.** The consumption-side guard is merged; the source still calls the producer-side bookkeeping bug a follow-up root cause.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #4](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/4), read on 2026-08-21, including the linked issue #2 A/B investigation.

**Symptom.** A long-context DSpark deployment survives ordinary traffic, then dies with `indexSelectSmallIndex` / device-side-assert behavior during request churn, especially when the active batch shrinks. Earlier asynchronous traces can falsely implicate unrelated kernels.

**Mechanism.** The reported DSpark draft sliding-window KV ring buffer has one row per request slot. Per-request `slot_index` values can go stale across request-condensation events. A stale id greater than or equal to the number of ring-buffer rows reaches draft KV gathers and trips the device index assertion. The source fix clamps slot ids on-device at all three affected draft gather sites. Because this is the speculative **draft** path, the source argues a clamped/wrong draft lookup can at worst propose a token the target rejects, trading acceptance for survival rather than corrupting accepted output.

The reported A/B is unusually strong: seven baseline runs died in 76-142 minutes; two runs with both long-context fixes completed four hours clean at about 117.5K and 115.8K context; disabling only the slot clamp reproduced the same assert at about 120 minutes at a 6 -> 5 request-condensation tick. Reported speculative acceptance was unchanged by the guard.

**What we have not done.** We have not reproduced the crash or the clamp A/B on our own DSpark lane. The source says the clamp is a consumption-side safety guard; the upstream producer of stale slot ids around condensation remains the deeper correctness target.

## If you have this stack

Pin the affected build and use a seed-pinned workload that repeatedly grows long-lived conversations while changing batch occupancy. Log request-slot assignment, condensation events and every draft `slot_index`. Compare the guard enabled versus disabled without changing the rest of the runtime. Preserve journal/device asserts as ground truth rather than relying only on health-probe timeouts.

**CONFIRM.** The failing arm presents an out-of-range draft slot id at or immediately around request condensation and the same seed/config survives when the on-device guard is enabled; disabling the guard restores the same assertion class.

**REFUTE.** Slot ids remain in range through the allegedly failing condensation event, or the matched guard-on/guard-off A/B has identical survival and failure signatures.

## Attribution

Reported, root-caused and A/B-tested by @paulbrav; merged by @tonyd2wild in PR #4. A second-rig reproduction was also reported in the linked issue thread. The registry has not independently reproduced the mechanism.
