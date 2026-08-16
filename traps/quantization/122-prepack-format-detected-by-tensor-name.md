# Trap 122: an expert prepack picks its decoder from tensor names, not dtype

**Found by tonyd2wild.**

**Status: under test.** The detection logic is readable in public source and
the name/dtype collision is demonstrable against a public checkpoint, but we
did not run the pack and therefore never observed the corrupted output. Filed
with CONFIRM/REFUTE criteria rather than as a confirmed trap.

**Symptom (predicted).** An offline expert-prepack step completes without
error against a checkpoint whose tensors are named like the expected format
but stored in a different dtype. The resulting planes load, the server starts,
and generation is degraded or nonsense. No crash, no warning, no dtype
assertion anywhere in the path.

**Mechanism.** `spark/prepack_planes.py` selects the source quantization
format by regex over **tensor names**, then dispatches unconditionally to a
dtype-specific decoder:

```python
fmt = "fp8" if any(PAT_FP8.match(n) for n in wm) else "mxfp4"
...
as_bytes = fmt == "mxfp4"
K13 = w13.shape[1] * (2 if fmt == "mxfp4" else 1)
...
codes, sbytes, _ = fp8_block_to_codes_scales(wg, sg)   # fp8 branch
codes, sbytes    = mxfp4_to_codes(wg), sg              # mxfp4 branch
```

The two patterns are documented in the file's own header:

```
mxfp4 : DS4-Flash-style  layers.L.ffn.experts.E.{w1,w2,w3}.{weight,scale}
fp8   : GLM-5.2-FP8-style model.layers.L.mlp.experts.E.
        {gate_proj,up_proj,down_proj}.{weight,weight_scale_inv}
```

The exposed case is a checkpoint that satisfies the **mxfp4 name pattern**
while holding **fp8 e4m3 data**. Republished and repacked community
checkpoints do exactly this. One we inspected declares

```json
{"fmt": "e4m3", "quant_method": "fp8",
 "weight_block_size": [128, 128], "scale_fmt": "ue8m0"}
```

in `config.json` while naming its experts
`layers.N.ffn.experts.M.w{1,2,3}.{weight,scale}` — the mxfp4 pattern. The
detector would route fp8 bytes through `mxfp4_to_codes()`, and `K` would
additionally be doubled by the 4-bit packing assumption against 1-byte fp8
storage.

Name-based detection is the general hazard here: names travel through repacks
and renames, dtypes do not, and the two drift apart silently.

**Stacks and builds bitten.** `Sapid-Labs/vLLM-Moet`, branch `spark-gb10`,
`spark/prepack_planes.py` (196 lines as read). Any pipeline inferring weight
format from tensor names rather than reading dtype or `quantization_config`.
Read on a DGX Spark GB10 fleet while evaluating a locally-held fp8 checkpoint
as a substitute prepack source.

**The check.** Compare what the detector would conclude against what the
checkpoint declares and stores:

```bash
python3 - <<'PY'
import json, glob, struct, os
M = "<checkpoint dir>"
cfg = json.load(open(os.path.join(M, "config.json")))
print("declared:", cfg.get("quantization_config", {}))
f = sorted(glob.glob(os.path.join(M, "model-*.safetensors")))[0]
with open(f, "rb") as fh:
    n = struct.unpack("<Q", fh.read(8))[0]
    hdr = json.loads(fh.read(n))
dt = {}
for k, v in hdr.items():
    if isinstance(v, dict) and "dtype" in v:
        dt[v["dtype"]] = dt.get(v["dtype"], 0) + 1
print("actual shard dtypes:", dt)
PY
```

A name pattern implying mxfp4 while `quant_method` is `fp8`, or shard dtype is
`F8_E4M3`, is the mismatch.

**CONFIRM / REFUTE, pre-registered.** CONFIRM if packing an fp8-data,
mxfp4-named checkpoint completes without error **and** the served result
scores materially below the same base packed through the fp8 path on a fixed
deterministic prompt set. REFUTE if the packer raises, or if a shape or `K`
assertion catches the mismatch before planes are written.

**The fix (proposed, untested).** Detect from `quantization_config` and the
shard dtype rather than tensor names, and assert the two agree before
dispatching. Failing that, a loud error when names and dtype disagree is worth
more than a silent branch.

**Found.** 2026-08-15, while evaluating whether a locally-held fp8 checkpoint
could stand in for a 149 GB download as a prepack source. The substitution was
abandoned on this reasoning; the corrupted-output half was never run, which is
why this is filed as under test.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Source read:
`Sapid-Labs/vLLM-Moet@spark-gb10`, `spark/prepack_planes.py`.
