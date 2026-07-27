# Trap 10: the quant label is not the kernel path

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

**The fix.** Choose checkpoints whose format matches a kernel path your
hardware actually has. State the kernel path next to every published speed
number, because the label alone under-determines it.

**Found.** 2026-07-09; hardware claim verified locally 2026-07-10.

**Attribution.** Blackwellboy.
