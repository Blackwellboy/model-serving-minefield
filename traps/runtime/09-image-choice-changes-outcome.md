# Trap 09: same weights, same box, three images, three different outcomes

**Status: reproduced here** (one checkpoint, three container images, identical two-node DGX Spark hardware).

**Symptom.** A model "works" or "does not work", or is fast or slow, and the
conclusion gets attached to the model or the hardware. The actual variable
was the container image.

**Mechanism.** The image determines the toolchain (trap 08), which kernel
implementations exist, and which fallback paths a quant format can take.
Identical weights on identical hardware can hard-fail, OOM, or serve at
materially different speeds purely by image choice.

**Stacks and builds bitten.** Measured on a ~299B MoE FP4-expert checkpoint
across two DGX Spark GB10 nodes (TP=2), one weight set, three images:

1. A 13.2-toolchain image: **error 222** at marlin FP4 repack. Never served.
2. A 13.0-toolchain image with the same repack path: the repack transiently
   about doubled MoE weight memory, **OOM and swap-thrash on both nodes**.
   Never served.
3. A 13.0-default-toolchain image with prebuilt kernels
   ([eugr/spark-vllm](https://github.com/eugr/spark-vllm-docker)) on the
   NVFP4 sibling checkpoint: **serves at 13.1 tok/s single-stream**.

Separately, the serving path the working image takes is weight-only FP4 on
forward-compat sm_120 cubins, measured at roughly 40% below the native-FP4
target for this hardware. Correct output, reduced speed: the image also
picks your speed class, not just success or failure. Full story:
[Hy3 dual-Spark recipe](https://github.com/Blackwellboy/Hy3-295B-NVFP4-MTP-Dual-DGX-Spark)
(README and FINDINGS.md).

**The check.** Before concluding anything about a model, record the image
digest next to the result, and test any model-level conclusion on a second
image before publishing it. Treat "image + weights + hardware" as the unit
under test, never "the model".

**The fix.** Pin the image by digest in every recipe and every published
number. When a result surprises you, the image is a first-class suspect.

**Found.** 2026-07-09, public writeup in the Hy3 repo.

**Attribution.** Blackwellboy; eugr's image is credited as the working path.
