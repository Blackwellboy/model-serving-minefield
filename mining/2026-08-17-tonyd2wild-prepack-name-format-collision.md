# Candidate: an expert prepack picks its decoder from tensor names, not dtype

**Found by tonyd2wild.**

**Disposition: public source lead; not a canonical trap.** The format-selection
mechanism is directly readable in public source at `Sapid-Labs/vLLM-Moet`,
commit `2f1056c56a56e08c560c4b2109a4d298d94f2c6b`,
`spark/prepack_planes.py`. The contributor also inspected an FP8 checkpoint
whose expert names match the MXFP4 pattern, but the exact public checkpoint
revision is not pinned and the mismatched pack was deliberately not run.
No replication is actually running, so the repository's closed status
vocabulary does not permit this to be labelled `under test`. The predicted
corrupted-output half is **not** claimed as observed; CONFIRM/REFUTE criteria
remain pre-registered below so the lead can be promoted cleanly if somebody
runs it.

**Predicted failure shape (not observed).** An offline expert-prepack step accepts a checkpoint
whose tensor names look like one supported source format while the stored
weights/config describe another. If no later shape/dtype guard catches that
mismatch, the wrong decoder can be selected before planes are written. What the
served output would look like on the reported FP8/MXFP4-name collision **has not
been run or observed**.

**Mechanism.** At the pinned source revision,
`spark/prepack_planes.py` chooses the source quantization format from regexes
over the checkpoint **weight-map names**:

```python
fmt = "fp8" if any(PAT_FP8.match(n) for n in wm) else "mxfp4"
...
as_bytes = fmt == "mxfp4"
K13 = w13.shape[1] * (2 if fmt == "mxfp4" else 1)
...
codes, sbytes, _ = fp8_block_to_codes_scales(wg, sg)   # fp8 branch
codes, sbytes    = mxfp4_to_codes(wg), sg              # mxfp4 branch
```

The source header defines the two naming conventions as:

```
mxfp4 : DS4-Flash-style  layers.L.ffn.experts.E.{w1,w2,w3}.{weight,scale}
fp8   : GLM-5.2-FP8-style model.layers.L.mlp.experts.E.
        {gate_proj,up_proj,down_proj}.{weight,weight_scale_inv}
```

The contributor's candidate collision is a checkpoint whose expert names match
the MXFP4 pattern while its quantization metadata describes FP8 E4M3 storage,
including values of the form:

```json
{"fmt": "e4m3", "quant_method": "fp8",
 "weight_block_size": [128, 128], "scale_fmt": "ue8m0"}
```

with expert names shaped like
`layers.N.ffn.experts.M.w{1,2,3}.{weight,scale}`. On the pinned prepacker that
name shape selects the MXFP4 branch; `as_bytes` becomes true and K is doubled
for the 4-bit packing assumption. The code does not first establish that the
selected branch agrees with checkpoint quantization metadata or shard dtype.

That source-level mismatch is the finding we can inspect publicly today. The
claim that it necessarily completes packing and produces corrupted served
output remains the experiment.

**Stacks and builds bitten.** Source inspected: `Sapid-Labs/vLLM-Moet`, commit
`2f1056c56a56e08c560c4b2109a4d298d94f2c6b`, `spark/prepack_planes.py`.
The broader risk applies to any conversion pipeline that infers weight format
from names while allowing repacks/renames to preserve those names independently
of dtype or quantization metadata.

**The check.** Compare what the name detector would infer against both declared
metadata and actual shard dtype before invoking a destructive/offline pack:

```bash
python3 - <<'PY'
import json, glob, struct, os, re
M = "<checkpoint dir>"
cfg = json.load(open(os.path.join(M, "config.json")))
print("declared:", cfg.get("quantization_config", {}))
idx = json.load(open(os.path.join(M, "model.safetensors.index.json")))
names = list(idx["weight_map"])
pat_mx = re.compile(r"^layers\.\d+\.ffn\.experts\.\d+\.w[123]\.(weight|scale)$")
pat_fp = re.compile(r"^model\.layers\.\d+\.mlp\.experts\.\d+\.(gate_proj|up_proj|down_proj)\.(weight|weight_scale_inv)$")
print("name detector:", "fp8" if any(pat_fp.match(n) for n in names) else "mxfp4")
f = sorted(glob.glob(os.path.join(M, "model-*.safetensors")))[0]
with open(f, "rb") as fh:
    n = struct.unpack("<Q", fh.read(8))[0]
    hdr = json.loads(fh.read(n))
dt = {}
for _, v in hdr.items():
    if isinstance(v, dict) and "dtype" in v:
        dt[v["dtype"]] = dt.get(v["dtype"], 0) + 1
print("actual shard dtypes:", dt)
PY
```

A name detector selecting MXFP4 while `quant_method` says FP8 or relevant
weights are stored as `F8_E4M3` is enough to stop and investigate. It is **not**
by itself proof that the current prepacker will write bad planes; that requires
the CONFIRM arm.

**CONFIRM / REFUTE, pre-registered.** CONFIRM the output-corruption half only if
an immutable FP8-data/MXFP4-named checkpoint is pinned, packing completes
without a format/shape assertion, and the served result materially degrades
against the same base routed through a deliberately correct FP8 path on a fixed
deterministic prompt set. REFUTE that half if the packer or loader raises before
planes are accepted, or if the supposedly mismatched path resolves to the same
correct representation. Either outcome should keep the source-level lesson:
name-based format inference needs an agreement check against metadata/dtype.

**The fix (proposed, not yet validated on the candidate checkpoint).** Select
from `quantization_config` plus actual tensor dtype/shape, and fail loudly if
those disagree with the naming convention before dispatch. If names remain a
compatibility hint, treat them as one signal rather than the authority.

**Found.** 2026-08-15, while evaluating whether an FP8 checkpoint could stand
in for a large MXFP4-source download during prepack work. The contributor
stopped before running the suspect conversion, which is why this stays in the
mining layer instead of borrowing certainty from the source inspection.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Public source inspected:
`Sapid-Labs/vLLM-Moet`, commit
`2f1056c56a56e08c560c4b2109a4d298d94f2c6b`, `spark/prepack_planes.py`.
