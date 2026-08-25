# Trap 131: a parallel shard loader runs collectives during multi-node weight load, and on unified memory it wedges a rank

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Measured on the
finder's private 2x DGX Spark (GB10) lane on 2026-08-12. Blackwellboy has not
independently reproduced this lane. Conditions and counts below; the raw
startup failure log is in the finder's private deployment and is not
published.

**Symptom.** You switch the load format to a parallel shard loader to cut the
multi-node cold-start time. Weight load starts, progresses a few shards, then
a roughly ten-minute NCCL watchdog timeout takes the whole process group
down. The worker rank is left wedged: TCP accepts connections but the SSH
banner exchange never completes, node exporters never answer, and only a
physical power cycle recovers it. The load never prints its completion line.
The steady-state memory figure that made the change look safe is not the
number that matters.

**Mechanism.** This loader streams checkpoint shards and performs distributed
collectives (a torch broadcast, per the stack trace) inside its weight-load
path. On a unified-memory box the staging/bounce-buffer path has no separate
host RAM to spill into, so the binding constraint is the transient peak
during load, not steady-state weights plus KV. vLLM plumbed none of the
loader's controls (bounce-buffer size, reader thread count, GDS off switch),
so the only knob it did expose was already at its safest value, and there was
nothing left to turn down. The loader pipeline itself was already off, which
rules out queue depth. The wedge is a userspace memory starvation on the
worker, distinct from a kernel panic: the node stays reachable at L4 while
service initialization never completes.

**Stacks and builds bitten.** vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), two DGX Spark (GB10) nodes, tensor
parallel 2, stock DeepSeek-V4-Flash-0731 (~115 GB, 24 shards), loader
`fastsafetensors` 0.3.3. Measured: load reached about 29% (7/24 shards) in
~1.5 min, then the NCCL watchdog reported a 600,053 ms broadcast timeout and
aborted the process group; the head failed with `WorkerProc initialization
failed due to an exception in a background process`; no `Model loading took`
line was ever printed (baseline reaches it in 151 s; we waited 16 minutes).
On the previous dead boot's kernel log, NVRM allocation-retry noise counted
116 events versus 25 on a healthy boot and 58 on an ordinary cold start, so
the messages are normal retry noise on GB10 and only the degree changed. The
steady-state figure of 0.65 of RAM looked safe; the 0.85-of-peak warning was
the one that applied. After revert to the default loader the same node loaded
reproducibly (224 s, twice, with the runtime gate 16/16 PASS).

**The check.** Before enabling a new loader, answer two questions rather than
one. First: can the default loader's completion line ("Model loading took
...") be used as a baseline? Record it, then compare. Second: is the memory
envelope computed as a PEAK (weights + loader transient + KV), not steady
state? If the loader exposes pipeline depth or bounce-buffer controls, verify
each is at its safest value and confirm there is nothing left to turn down.
During the load, watch the worker for the wedge signature: ports accept but
initialization encounters never complete. A TCP probe is not a liveness
probe here.

**The fix.** Stay on the default loader on this hardware until the loader
exposes controls for its staging path (bounce buffers, thread count, GDS
off), or a newer version changes the default envelope. Treat the node as
requiring a physical power cycle once wedged at this depth; nothing remote
recovered it. Revisit only with a knob that can go lower, on a node that can
afford a power cycle if it is wrong.

**Found.** 2026-08-12, when the parallel-loader A/B wedged the worker and the
lane rolled back to the default loader.

**Attribution.** @sethforprivacy. Raw startup log and the wedge investigation
are in the finder's private deployment and were not published.

**Related.** [115](../evaluation/115-exit-137-is-not-oom-killer-proof.md), [116](116-successful-load-does-not-prove-first-forward-dtype-path.md), [123](123-vllm-v1-enginecore-orphan-holds-gpu-memory.md), [119](../memory/119-free-memory-drifts-down-after-churn.md), [08](08-image-toolchain-newer-than-driver.md).
