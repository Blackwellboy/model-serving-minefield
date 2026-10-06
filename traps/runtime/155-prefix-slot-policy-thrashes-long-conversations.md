# Trap 155: prefix-slot victim policy can make two long conversations repeatedly re-prefill

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #169](https://github.com/Blackwellboy/model-serving-minefield/issues/169)); a later measured victim-selection patch is documented in the issue thread.

**Symptom.** New conversations reuse a long shared system prefix correctly, yet two long alternating conversations repeatedly cache only that system block. Each turn re-reads tens to hundreds of thousands of prior tokens, producing large first-token delays with no error or memory warning.

**Mechanism.** On the measured TensorFold Flash Next path, a fork could use only a free slot. An idle-but-not-free slot retained an unrelated prefix, so both active conversations alternated through the same slot and evicted each other's post-system state. Source replay reproduced almost all measured cache counts. A later fewest-kept-tokens victim rule on a newer pinned build reduced the measured two-slot wait by roughly 73% while preserving output hashes.

**Stacks and builds bitten.** TensorFold 0.6.1 Flash Next / qwen4_exp, `--parallel 2`, long Qwen3.8-Flash-Next-family conversations on DGX Spark. The initial sequence began after earlier traffic; do not claim every clean boot reproduces it.

**The check.** Record `cached_tokens` per next turn. If it remains a constant equal to the shared system prefix instead of tracking the previous conversation length, inspect slot residency/victim selection rather than model speed.

**The fix.** Use a slot/victim policy that can reclaim an idle retained slot based on re-prefill cost, or provide enough slots for the active long conversations and intervening tasks. Validate with output-hash controls.

**Found.** 2026-10, long-conversation prefix-residency study.

**Attribution.** @scottleimroth.
