# Trap 47: a stale deployed binary misses its own arch-native kernel, and the tell is power draw

**Found by TheTom.**

**Status: reproduced here.** Before/after on the same box, same model, same flags; raw
`nvidia-smi` samples and server logs held outside the tree and can be produced on request, per the
default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo).

**Symptom.** A 27B 4-bit model decodes at **~16 tok/s** on hardware that should do 40 to 100.
Nothing
errors. The natural conclusions are all wrong: that this quant format is slow on this card, that
this model is heavy, that the fix is not upstream yet.

**Mechanism.** The running binary predated the upstream native-FP4-for-Blackwell kernel, so 4-bit
ran through a generic scalar/dp4a fallback even though the hardware supports a native tensor-core
dispatch. **The fix was already merged into the branch the deployment tracks. Production had simply
never been rebuilt.** Nothing needed porting; there was no missing commit.

Third sibling to [trap 10](../quantization/10-quant-label-is-not-the-kernel-path.md): trap 10 is
"the checkpoint can only take one path", trap 46 is "your cmake line decided which paths exist", and
this is "the path exists in the source you track but not in the binary you are running." Same
consequence, the quant label promises a kernel you are not executing, reached three different ways.

**Stacks and builds bitten.** llama.cpp on consumer Blackwell (sm_120), running a binary older than
the upstream "Blackwell native NVFP4" merge. Generalizes to any fast-moving inference fork where the
serving binary and the branch tip drift.

**The check.** Two, in order of cheapness:

1. **GPU utilization vs power draw.** This is the tell, and it is architecture-agnostic:
   **98% `utilization.gpu` at ~270W of 575W (47% TDP)** means compute units are busy but tensor
   cores are not saturated, i.e. you are on a fallback path. After the rebuild the same workload ran
   **95% util at ~460W (80% TDP)** and 16 to 40 tok/s. Runnable:
   [`checks/util_vs_power_tell.sh`](../../checks/util_vs_power_tell.sh).

   ```
   $ bash checks/util_vs_power_tell.sh 30
     mean util 97.8%   mean power 271W / 575W (47% TDP)
     VERDICT: high-util / low-power, suspect fallback kernel, check build provenance
   ```

2. **Ancestry, before you assume a fix needs porting:**

   ```bash
   git merge-base --is-ancestor <fix-commit> <running-HEAD> && echo "present" || echo "STALE"
   ```

   Also confirm the feature actually compiled in, the server's startup `system_info` line reports
   the arch-native flag (`BLACKWELL_NATIVE_FP4 = 1` in this case). A flag you passed is not
evidence;
   a banner the binary printed is.

**The fix.** Rebuild from the branch tip in an **isolated `git worktree`** so the live server is
undisturbed during the build, mirroring the production CMake cache. Then cut over.

**Cutover gotcha.** `kill <pid>` (SIGTERM) left the old server in uninterruptible sleep (`D` state)
for 5+ seconds still holding VRAM, so the new binary could not allocate. `kill -9` was required. On
a single-GPU box you also cannot run old and new side by side to A/B, so capture the before-numbers
first.

**Two follow-on lessons from the same incident**, both of which would otherwise have been attributed
to the model:

- **Fixing the kernel was not the whole story.** The server fronted a gateway routing ~10 auxiliary
  tasks to the same port; at one slot, every one serialized behind the user's turn. Three parallel
  10-token requests finished at 825 / 1082 / 1405 ms, strictly serial. Two slots fixed it and VRAM
  moved 27.9 to 28.0 GB, because context is *split* across slots, not multiplied.
- **"This file has no MTP" is not "this family has no MTP."** The deployed quant lacked
  multi-token-prediction tensors, so the speculative flag made the server refuse to start. A
  purpose-built MTP-preserving quant of the same weights initialized fine and took decode from a
  43 tok/s non-MTP ceiling to **~83 tok/s**.

**Found.** 2026-07-05.

**Attribution.** TheTom.
