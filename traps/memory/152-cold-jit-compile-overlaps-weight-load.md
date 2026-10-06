# Trap 152: first-start CUDA JIT memory can overlap streaming weights on unified-memory hosts

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #162](https://github.com/Blackwellboy/model-serving-minefield/issues/162)).

**Symptom.** A model shape passes the engine's startup capacity estimate but a first start after install/cache wipe drives host unified memory to a watchdog threshold while weights are still loading.

**Mechanism.** The engine JIT-builds CUDA extensions on first use while the checkpoint is simultaneously streaming into the same GB10 physical memory pool. The engine admission estimate accounts model/cache geometry but not compiler working memory, so compilation pressure lands on top of the weight-load peak. A warm kernel cache hides the condition on later boots.

**Stacks and builds bitten.** TensorFold 0.5.0 CUDA, DGX Spark GB10, large MLX-format Qwen3.8-Flash-Next-family model, empty kernel cache.

**The check.** On first start after any engine/cache change, record `MemAvailable` and build-log events through the entire load. Compare with a control where required extensions are prebuilt in a weight-free container.

**The fix.** Prebuild serve-path extensions before the real model boot, persist the kernel cache keyed by engine/toolchain identity, and detect stale build locks after killed compiles.

**Found.** 2026-09, first boot of a large TensorFold lane.

**Attribution.** @scottleimroth.
