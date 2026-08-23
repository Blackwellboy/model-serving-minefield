# Trap 125: cgroup v2 `MemoryMax` does not account DGX Spark CUDA unified-memory allocations

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #57](https://github.com/Blackwellboy/model-serving-minefield/issues/57)). The contributor measured the CUDA and host-allocation controls on DGX Spark; Blackwellboy has not independently reproduced this lane.

**Symptom.** A systemd/cgroup v2 `MemoryMax` guard around a model server looks armed, but a CUDA allocation can grow beyond the configured limit without the cgroup killing the process. On the reported DGX Spark test, a 12 GiB CUDA allocation completed inside an 8 GiB `MemoryMax` scope while `memory.current` only reached about 409 MiB. A plain host-memory control in the same scope shape was killed at the limit.

**Mechanism.** On the measured GB10 unified-memory path, the CUDA driver-side allocation was not charged to the cgroup's `memory.current` in proportion to the physical memory it consumed. The cgroup therefore had nothing equivalent to the CUDA footprint to enforce against. The small rise that was visible was consistent with bookkeeping/page-table overhead, not the allocation itself. This is a measured platform/runtime behavior, not a claim that every CUDA or every unified-memory implementation behaves this way.

**Stacks and builds bitten.** NVIDIA DGX Spark / GB10 (`sm_121`), Ubuntu 24.04 aarch64, cgroup v2 with the memory controller delegated to the user slice; CUDA allocations observed from a vLLM 0.26-line serve and a standalone PyTorch allocator. The contributor used `systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0`. Broader Grace-Blackwell or CUDA-UMA applicability is unmeasured here.

**The check.** First prove the limiter itself with a positive control: run a plain host allocator in an 8 GiB scope with `MemorySwapMax=0`, grow in 1 GiB steps, and require an exit near the limit plus an `oom_kill` increment in `memory.events`. Then repeat the same growth pattern with CUDA while watching both `memory.current` and `/proc/meminfo` `MemAvailable`. If physical available memory falls with the CUDA allocation while `memory.current` remains far below the configured cap and no cgroup OOM event fires, `MemoryMax` is not a valid CUDA guard on that lane. Do not omit the swap control: with swap allowed, even the host control can survive and make a broken test look healthy.

**The fix.** Do not treat `MemoryMax` as the sole last-resort guard for CUDA unified-memory pressure on a lane that reproduces this check. The contributor's measured workaround is an off-box or independent watchdog on `/proc/meminfo` `MemAvailable`, using consecutive-breach hysteresis so legitimate load/KV transients do not trigger a kill. When terminating a failed serve, also account for child GPU-owning processes rather than assuming the API-server PID owns all allocations; see [Trap 123](../runtime/123-vllm-v1-enginecore-orphan-holds-gpu-memory.md).

**Found.** 2026-08-23 while testing a safety guard motivated by DGX Spark unified-memory over-allocation risk.

**Attribution.** @scottleimroth. Original measured report and controls: [issue #57](https://github.com/Blackwellboy/model-serving-minefield/issues/57). Related: [Trap 13](13-utilization-fraction-on-unified-memory.md), [Trap 96](96-list-devices-reports-host-memory-as-device-free-memory.md), [Trap 115](../evaluation/115-exit-137-is-not-oom-killer-proof.md), [Trap 123](../runtime/123-vllm-v1-enginecore-orphan-holds-gpu-memory.md).
