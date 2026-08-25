# Trap 132: the first request after a cold start pays kernel JIT compilation, and it reads as a wedge and contaminates your A/B

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Measured on the
finder's private 2x DGX Spark (GB10) lane on 2026-08-16. Blackwellboy has not
independently reproduced this lane. Conditions and numbers below; raw logs
are private.

**Symptom.** A freshly booted lane looks wedged: GPU utilization pinned near
96%, both token counters at zero, and a request that normally finishes in
about 22 seconds running past 10 minutes. It is not a wedge, it is
just-in-time kernel compilation. And any A/B run inside this window is
contaminated: whichever arm runs first absorbs the one-off cost and looks
worse, so the comparison is wrong in a direction you can defend in prose but
not on the hardware.

**Mechanism.** The first inference after a cold boot triggers JIT compilation
(CuTeDSL, Triton, and the flashinfer autotuner on this stack) for kernels
whose build products were not persisted. The generation and prompt token
counters advance only on request completion, so a long first request leaves
both pinned at zero while the GPU is busy, which is exactly the signature of
a hang. The truth is in the worker log: kernel names and "perf cliff"
warnings next to the long latency.

**Stacks and builds bitten.** vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), two DGX Spark (GB10) nodes, stock
DeepSeek-V4-Flash-0731, DSpark speculative decoding, flashinfer autotuner
on. Measured: a 32K cold prefill that reads ~22 s on a warm cluster had not
completed after 10+ minutes on a fresh boot, GPU at 96%, both vLLM token
counters at zero; the worker log carried `CuTeDSL JIT compilation during
inference: W4A16FusedMoeKernel. This causes a latency spike`, `Triton kernel
JIT compilation during inference: _build_prefill_chunk_metadata_kernel`, and
`flashinfer.jit [AutoTuner]: No tuned config covers sparse_mla_... ... perf
cliff`. A subsequent A/B run on a cluster that had been up 26 h had none of
this; the finder's clean clock-cap numbers were produced under that
condition.

**The check.** When a fresh lane looks stuck, read the container log before
killing anything: look for JIT-compilation lines with the GPU busy and both
token counters at zero. Those counters advance on completion, so zero is
expected while a long first request is still in flight. Before benchmarking
after any boot, warm the lane and wait until a normal request completes at
normal latency.

**The fix.** Put a warmup request in the boot path, or simply treat the first
~10 minutes after a cold start as non-benchmarkable. Write "was the cluster
warm" into the A/B runbook next to the other conditions; it is a real
confound that looks nothing like one.

**Found.** 2026-08-16, when a post-reboot verification pass looked like a
hang and a later A/B motivation re-opened the question.

**Attribution.** @sethforprivacy. Raw boot logs are in the finder's private
deployment and were not published.

**Related.** [54](54-run-order-and-warm-cache-artifacts.md), [110](110-unscreened-bench-on-a-shared-endpoint.md), [46](../versioning/46-stale-build-missing-arch-kernel.md), [107](../memory/107-soak-duration-changes-the-verdict.md).
