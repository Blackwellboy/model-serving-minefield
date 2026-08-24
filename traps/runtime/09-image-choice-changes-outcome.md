# Trap 09: same weights, same box, three images, three different outcomes

**Found by Blackwellboy; working path by eugr.**

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

## Added 2026-08-25: a bind-mounted runtime overlay changed behavior with the image digest and weights unchanged

**Status of this addendum: measured here, raw not published.** This is a
supporting instance that sharpens the unit-under-test rule; it is not a new
public trap number.

On a single DGX Spark serving DeepSeek-v4-Flash 0731 EXL3 with DSpark K5, the
checkpoint bytes and container image digest were held fixed while an opt-in,
read-only `model.py` overlay projected a published refusal direction out of the
attention output stream at runtime. The overlay was enabled with `ABLATE=1`,
`lambda=3.5`, layers 10-42. No model weights were edited or re-downloaded.

The behavioral result changed dramatically despite identical weight identity
and unchanged image digest:

- thinking off: **8/8 refusals -> 0/8**;
- thinking on: **7/8 refusals -> 0/8**.

A small matched capability smoke showed no obvious regression: stock and
runtime-ablated arms both scored 6/6 with thinking off and 2/6 with thinking on;
the thinking-on misses were the same empty-content-at-length/reasoning-budget
artifact in both arms. Performance did not regress in the matched cells: code
was **36.621 -> 36.985 tok/s** and prose **21.841 -> 22.812 tok/s**. DSpark
acceptance also stayed effectively flat/slightly higher (code **0.5463 ->
0.5477**, prose **0.2568 -> 0.2710**). A 13,558-token retrieval sanity check
passed with no NaNs.

This instance exposes a boundary in the original wording: **pinning the image
digest is necessary but not sufficient when runtime code can be bind-mounted or
otherwise overlaid.** The practical unit under test is at least:

`image digest + weights + mounted/overlaid code + runtime config + hardware`.

**The extra check this instance adds:** record read-only bind mounts, injected
model-code overlays, and compile/AOT cache identity next to the image digest.
When toggling an overlay, prove from the live process/logs that the intended code
is actually mounted and active; otherwise a supposedly matched A/B can compare
stale compiled code to the new configuration.
