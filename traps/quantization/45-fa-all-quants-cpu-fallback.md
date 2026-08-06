# Trap 45: unsupported KV quant pairs silently fall back to CPU, and the bench tool does not error

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Symptom.** Prefill collapses ~20x (about 1500 to about 70 tok/s) and decode roughly halves (152
to 90) for
certain K/V quant combinations. `llama-bench` prints a clean table and **does not warn, error, or
mark the row**. The obvious reading is "this KV quant is slow", and that reading gets published.

**Mechanism.** The CUDA/HIP flash-attention path only compiles kernels for a subset of K/V quant
pairs unless the build enables all of them. Unsupported pairs silently take a much slower
non-tensor-core path. Nothing in
the runtime says so; you only see it in the throughput.

This is [trap 10](10-quant-label-is-not-the-kernel-path.md)'s lesson, the label is not the kernel
path, in its **build-flag** form: here the checkpoint and the arch are both fine, and it is your own
`cmake` line that decided which kernels exist. Same class, different lever, and it applies to the KV
cache rather than the weights.

**Stacks and builds bitten.** **Measured on HIP/ROCm 7.2, gfx942, only.** The CUDA half is
source-inferred: the same build flag gates the same kernel set, but we did not run it on an
NVIDIA box, so treat CUDA as untested here. What was measured is the throughput collapse and
its signature; that the slow path is literally CPU-resident is an inference from the magnitude,
not something we instrumented. llama.cpp builds without `-DGGML_CUDA_FA_ALL_QUANTS=ON`. Asymmetric combos such as
`q8_0` K with `q4_0` V are the common victims. Note that a fork may carry a narrow patch covering
only one specific combination (e.g. f16/bf16 K with `q8_0`), which makes the problem *look* fixed
while every other pair still falls back.

**The check.** The signature itself, ~20x prefill drop with ~0.5x decode, no error, is
diagnostic. Confirm by running the same model on the same binary at `f16/f16` and comparing; then
check how the build directory was configured.

```bash
# 1. baseline on the same binary
llama-bench -m $MODEL -ngl 99 -p 512 -n 128 -ctk f16  -ctv f16
# 2. the suspect pair
llama-bench -m $MODEL -ngl 99 -p 512 -n 128 -ctk q8_0 -ctv q4_0
# a ~20x prefill gap between these two is a build-config artifact, not a KV-quant result
```

**The fix.** Build the comparison binary with the flag, and keep it as a *separate* build directory
so you always know which one produced a number:

```bash
cmake -DGGML_HIP=ON -DGPU_TARGETS=gfx942 -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=/opt/rocm/bin/hipcc -DCMAKE_CXX_COMPILER=/opt/rocm/bin/hipcc \
      -DGGML_CUDA_FA_ALL_QUANTS=ON \
      -B build-allquants
cmake --build build-allquants -j 16
```

(CUDA is the same flag with `-DGGML_CUDA=ON` and `-DCMAKE_CUDA_ARCHITECTURES=<arch>`.)

**Any KV-pair result from a default build is a build-config artifact and must be discarded, not
caveated.** Record the build directory and its CMake flags alongside every KV-quant number.

**Adjacent gotcha, same family.** `AMDGPU_TARGETS` is deprecated in favor of `GPU_TARGETS` (both
still work); and `ROCBLAS_USE_HIPBLASLT=0` is worth setting on ROCm 7.2 for certain shapes, mostly
affecting long-context prefill.

**Found.** 2026-04-29, on the first clean KV-quant comparison matrix for a cloud AMD node, the
first pass had already produced a full set of polluted numbers.

**Attribution.** TheTom.
