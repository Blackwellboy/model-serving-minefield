# Trap 154: an engine upgrade can change NVFP4 arithmetic behind an unchanged launch line

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #168](https://github.com/Blackwellboy/model-serving-minefield/issues/168)).

**Symptom.** After an engine upgrade, the same checkpoint and nearly identical launch line starts faster and passes health checks, but a long greedy generation produces different token hashes. An old precision-related flag may also become invalid.

**Mechanism.** TensorFold 0.6.1 introduced `--precision checkpoint|full` and defaulted to checkpoint arithmetic for the measured NVFP4 family. The prior 0.6.0 path corresponds to 0.6.1 `--precision full`. Therefore the default upgrade changes activation arithmetic even though the checkpoint/model name is unchanged.

**Stacks and builds bitten.** TensorFold 0.6.0 `c464617...` versus 0.6.1 `17c73e1...`, Qwen3.8-27B-family NVFP4 on DGX Spark GB10. Flash Next had a separate boundary where `--precision full` was a no-op.

**The check.** After an engine upgrade, pin explicit precision and run long greedy token-hash witnesses, not only short prompts. Compare startup-resolved precision and reject unsupported legacy flag combinations.

**The fix.** Put the intended arithmetic mode explicitly in the launch configuration and requalify any score produced under a different resolved mode.

**Found.** 2026-10, TensorFold upgrade qualification.

**Attribution.** @scottleimroth.
