# Trap 10: the quant label is not the kernel path

**Found by Blackwellboy.**

**Status: reproduced here** (DGX Spark GB10; one hard failure, one measured speed class), backed by a claim-scoped hardware note.

**Symptom.** A checkpoint marketed by its quant format ("NVFP4", "MXFP4")
serves far slower than the format promises, or fails outright, and the repo
name gave no warning. Two checkpoints with the same label take completely
different code paths. "It is NVFP4 so it will be fast on FP4 hardware" turns
out to be false on your box.

**Mechanism.** Two independent gaps between the label and reality:

1. **The label does not say which kernels can run it.** What matters is the
   `config.json`: `quant_method`, the per-tensor/per-layer quantization
   schemes, and whether the format matches a kernel family your build
   actually ships for your arch. On GB10 (sm_121) there is no native FP4
   tensor pipe, so community `compressed-tensors` MXFP4/NVFP4 MoE
   checkpoints all route to **weight-only Marlin** repack regardless of any
   env flag claiming otherwise. We watched `VLLM_USE_B12X_MOE=1` do nothing:
   the quant method routed to `prepare_moe_fp4_layer_for_marlin` anyway.
2. **"NVFP4" packages are often mixed-precision.** Real packages we have
   served include an FP8-base-plus-FP4-expert build and an NVFP4-spine
   EXL3-tail hybrid. The fast serving paths are **format-matched end to
   end** (quant format, kernel family, and drafter all matched); a checkpoint
   that merely contains FP4 tensors somewhere does not get that path.

The measured consequence on this hardware class: the marlin-bound NVFP4
route serves a ~295B MoE at 13.1 tok/s while a format-matched
FP8-base/FP4-expert stack of comparable scale runs several times faster on
the same boxes. The slowness is a property of the only kernel path the
checkpoint can take, not a tuning miss. Public writeup:
[Hy3 dual-Spark recipe](https://github.com/Blackwellboy/Hy3-295B-NVFP4-MTP-Dual-DGX-Spark)
(hypothesis-disproven section in FINDINGS.md).

**Stacks and builds bitten.** vLLM on DGX Spark GB10 (sm_121), community
MXFP4 and NVFP4 compressed-tensors checkpoints of a ~295B MoE; the MXFP4
attempt never served at all (trap 08 and trap 09 for the failure modes).

**The check.** Before downloading 160 GB, read the config, not the repo
name:

```bash
python3 -c "import json,sys; c=json.load(open('config.json')); \
print(c.get('quantization_config',{}).get('quant_method')); \
print(json.dumps(c.get('quantization_config',{}),indent=1)[:2000])"
```

Then answer: which kernel family does this `quant_method` route to in YOUR
build on YOUR arch, and is that the fast path or a weight-only fallback? If
you cannot answer from the config plus your build, expect the fallback.

**The fix.** Choose checkpoints whose format matches a kernel path your hardware actually has. State the kernel path next to every published speed
number, because the label alone under-determines it.

**Found.** 2026-07-09; hardware claim verified locally 2026-07-10.

**Attribution.** Blackwellboy.

## Added 2026-07-28: two more instances, failing in opposite directions

**NVIDIA Nemotron 3 family, three checkpoints (Nano 30B A3B NVFP4, Nano Omni 30B A3B NVFP4, Super 120B A12B NVFP4), GB10-class single nodes, vLLM 0.20.0 and 0.25.1.**

**The label is wrong about the checkpoint.** A repository named NVFP4 whose
`quantization_config.quant_algo` is **`MIXED_PRECISION`**: FP8 across 139
targets (attention and Mamba projections, latent projections, shared expert),
NVFP4 at W4A4 group size 16 across 40,961 targets (the routed experts). The
engine resolves it to `quantization=modelopt_mixed` and selects **two** kernels,
one per scheme. The Hugging Face API tags the repository **`8-bit`**, not
`4-bit`. Practically: your stack needs both an FP8 and an NVFP4 kernel path, and
a stack with only one of them fails or falls back silently.

**The label is right about the checkpoint and still says nothing about the
kernel.** Two genuine-NVFP4 siblings both bound to `FLASHINFER_CUTLASS` out of
seven candidate MoE backends, with `MARLIN` and `EMULATION` both available and
either of which would have been accepted silently. On the mixed-precision member
the vendor launch line **forces** Marlin with three separate settings
(`VLLM_NVFP4_GEMM_BACKEND=marlin`, `--moe-backend marlin`,
`VLLM_USE_FLASHINFER_MOE_FP4=0`). Drop those and you are on a different kernel
path with different failure modes. The quantisation **packaging format**, not
the label, decides.

### The labelling pattern itself, which is now a second clean instance

This is worth separating from the kernel-path consequence above, because it is a
different problem with a different fix. The pattern: a repository name states a
quantisation format, and the format is either not what the file says or not what
the runtime does, and **neither disagreement produces any error**. The first
clean instance in this registry was a community MXFP4 or NVFP4
compressed-tensors upload routing to a weight-only fallback. This is the second,
and it fails one level earlier: the label disagrees with the checkpoint's own
`quantization_config` rather than with the kernel.

The generalisable rule, which costs one command: **read
`config.json`'s `quantization_config` before you believe a repository name, and
read the engine's own resolved quantisation line before you believe the
config.** Three things can disagree (name, config, resolved kernel) and each
disagreement is silent.

*Status of this addendum: reproduced here. The `quantization_config` block and
the HF `8-bit` tag are public and checkable without us; the backend binding is
in the engine's own startup log on any lane serving the checkpoint.*

## Added 2026-08-25: AutoRound export packing changed the speed class

**Status of this addendum: measured here, raw not published.** The full build
and benchmark packet is retained privately; the numbers below are the
claim-scoped summary from one RTX 5090 campaign.

A Qwen3.8-27B OBLITERATED W4A16/group-128 rebuild produced two artifacts that
could both casually be described as "AutoRound INT4", but they did not encode
the same runtime representation. The first export, made through
`--format auto_gptq`, identified as `quant_method=gptq`, carried `g_idx`, and
served through the GPTQ/Marlin path. A second rebuild reconstructed the known
fast reference packing as `auto_round:auto_gptq`, with `g_idx=0`, matched
qweight inventory, matched MTP treatment, and the same auxiliary-tensor size as
the reference artifact.

On the same RTX 5090, the same vLLM+DFlash2 stack and K7 speculative depth, the
packing change moved code decode from about **191.9 tok/s** to **233.1 tok/s**.
The matched non-abliterated Frozenlock reference measured **233.83 tok/s** in
the same session. Code speculative acceptance was likewise essentially matched
(**79.9%** OBLIT versus **80.3%** reference). Prose remained workload-sensitive:
OBLIT K7 measured **101.18 tok/s** versus **107.15 tok/s** reference, while the
same OBLIT target reached **109.43 tok/s** at K6.

The useful conclusion is narrower than "abliteration is free": **the earlier
~18% route-level gap was dominated by export/packing identity, not by the target
weight intervention.** Only after the packing and MTP treatment matched did the
code path return to reference-class speed. The matched behavior/correctness fixture remained green, but a separate tiny
eight-task intelligence smoke scored the Frozenlock reference **8/8** and the
matched OBLIT target **7/8** because of one strict tool-call-format near-miss.
That bounded miss is reported rather than hidden, and this experiment does
**not** establish universal intelligence equivalence.

**The extra check this instance adds:** for AutoRound/GPTQ-family artifacts,
do not stop at bits, group size and a marketing label. Record and compare
`quant_method`, export format, `g_idx` presence, packed tensor inventory,
auxiliary/MTP treatment, and the loader/kernel actually selected at runtime.
Two "W4A16 group-128 AutoRound" checkpoints can otherwise land in different
speed classes without an obvious launch error.
