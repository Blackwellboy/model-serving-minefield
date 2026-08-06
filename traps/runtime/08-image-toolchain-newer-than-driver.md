# Trap 08: image toolchain newer than the host driver kills kernels at JIT time

**Found by Blackwellboy.**

**Status: reproduced here** (two distinct kernel classes, two container images, DGX Spark GB10 fleet).

**Symptom.** The container starts, weights load, everything looks healthy,
and the serve dies at kernel-build time with
`cudaErrorUnsupportedPtxVersion` (error 222), or at first inference when a
JIT-compiled kernel is rejected. The failure names an internal kernel file,
not your config, so it reads like a broken model or a broken vLLM.

**Mechanism.** The image's default CUDA toolchain (`ptxas`/`nvcc`) is newer
than what the host driver's PTX JIT accepts. Any kernel that ships as PTX
and gets JIT-compiled at runtime is rejected. Kernels that ship as prebuilt
cubins for your arch are fine, which is what makes this confusing: the same
image can serve one model and kill another, depending on which kernel class
each model's quant path pulls in.

**Stacks and builds bitten.** Twice on DGX Spark GB10 (CUDA 13.0 driver):

- Marlin's NVFP4 repack on a CUDA 13.2-toolchain image: error 222 in
  `marlin_utils_fp4.py: repack_weight`. Not fixable by env vars
  (`TRITON_PTXAS_PATH` only affects Triton). Documented with the fix in
  [our Hy3 dual-Spark recipe](https://github.com/Blackwellboy/Hy3-295B-NVFP4-MTP-Dual-DGX-Spark#troubleshooting).
- A CuTe-DSL TMA attention kernel that JIT-compiles at first inference on a
  13.2-toolkit image over the 13.0 driver: loads clean, ready state, crashes
  on the first generation. The MoE kernels in the same image family work,
  because those are prebuilt cubins. Documented in
  [our MiniMax dual-Spark driver](https://github.com/Blackwellboy/MiniMax-M3-2x-DGX-Spark-stock-driver).
  The image label is not the compatibility story; the kernel class is.

**The check.** Before serving:

```bash
docker run --rm <image> bash -c 'which ptxas; ptxas --version'
nvidia-smi | head -3   # driver CUDA version
```

If the image's default toolchain is newer than the driver's CUDA, any
runtime-JIT kernel path is at risk. A load-then-crash-on-first-token pattern
on a "ready" server is this trap until proven otherwise.

**The fix.** Use an image whose default toolchain matches the driver (on a
13.0 driver, a 13.0-toolchain image), or a build whose kernels ship as
prebuilt cubins for your exact arch so nothing JITs from PTX.

**Found.** 2026-07-09 (marlin case, internal task log; public writeup in the
Hy3 repo) and 2026-07-23 (TMA case, public in the MiniMax repo).

**Attribution.** Blackwellboy.
