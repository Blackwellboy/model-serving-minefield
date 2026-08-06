# Trap 27: the NVFP4 checkpoint serves fast and answers garbage

**Found by @pavanimajety (accuracy report) and @cghart (ignore-list mechanism).**

**Status: reported by others** (a maintainer-filed vLLM accuracy bug and a
second issue that isolates a concrete config mechanism with an upstream
fix PR); not independently reproduced here.

**Symptom.** After moving to an NVFP4 (or MXFP4) checkpoint the model
"does not know basics", fails questions the original answers easily, or
produces outright garbage, while tok/s looks great and the load is clean.
Measured upstream: GSM8K 0.11 on the NVFP4 checkpoint versus 0.90 on the
original, same model
([vllm #36094](https://github.com/vllm-project/vllm/issues/36094),
maintainer-filed). Nothing in the logs says anything is wrong.

**Mechanism.** Several distinct config and build gaps produce the same
silent cliff:

1. **Ignore-list misses on hybrid architectures.** Community NVFP4 quants
   of Qwen3-Next-family models ship fused GDN projections
   (`in_proj_qkvz`, `in_proj_ba`) whose names do not match the
   checkpoint's `quantization_config.ignore` entries, so layers that must
   stay unquantized get quantized, and every such community quant tried
   produced garbage
   ([vllm #40252](https://github.com/vllm-project/vllm/issues/40252);
   upstream fix
   [PR #34697](https://github.com/vllm-project/vllm/pull/34697)).
2. **Engine-version-dependent kernel paths.** The same NVFP4 checkpoint
   reported fine on vLLM 0.18.0 and garbage on 0.19.0 in the #36094
   thread; accuracy is a property of checkpoint plus engine build, not of
   the format.
3. **Non-native hardware.** Serving an NVFP4 checkpoint on hardware
   without native FP4 support runs emulated or fallback paths whose
   accuracy is its own question (maintainer note in the same thread), on
   top of the speed penalty
   ([trap 10](10-quant-label-is-not-the-kernel-path.md)).
   MXFP4 MoE at `tensor_parallel_size=1` has separately produced
   incorrect expert outputs
   ([vllm #35329](https://github.com/vllm-project/vllm/issues/35329)).

Trap 10 is the speed half of this surface: the label does not tell you
which kernels run. This is the correctness half: the label does not tell
you the output is right, and speed dashboards actively mask it.

**Stacks and builds bitten.** `nvidia/Qwen3.5-397B-A17B-NVFP4` on vLLM
TP=2 (#36094); every community NVFP4 quant of Qwen3-Next-family hybrids
tried in #40252 (five named repos), reproducing on GB10 (sm_121) and
elsewhere; MXFP4 MoE at tp=1 (#35329).

**The check.** A ten-prompt factual probe at temperature 0 immediately
after first load, before any speed benching, compared against the
unquantized model's known answers. Then diff every module name in the
checkpoint against `quantization_config.ignore` and confirm the layers
the architecture requires unquantized actually match. Record the engine
version next to the accuracy number.

**The fix.** Use quant uploads and engine builds with the fix applied
(vLLM PR #34697 for the ignore-list class), re-validate accuracy on every
engine upgrade, and treat any quant accuracy claim without an engine
version as unscoped. Speed and accuracy are separate acceptances; passing
one says nothing about the other.

**Found.** 2026-07-27 (mined from upstream).

**Attribution.** @pavanimajety
([vllm #36094](https://github.com/vllm-project/vllm/issues/36094)),
@cghart
([vllm #40252](https://github.com/vllm-project/vllm/issues/40252) and fix
PR #34697), @zeryx
([vllm #35329](https://github.com/vllm-project/vllm/issues/35329)).
Related entries:
[trap 10](10-quant-label-is-not-the-kernel-path.md) (speed half),
[trap 09](../runtime/09-image-choice-changes-outcome.md) (the build
decides the path), and methodology rule 2 (build and revision next to
every number).
