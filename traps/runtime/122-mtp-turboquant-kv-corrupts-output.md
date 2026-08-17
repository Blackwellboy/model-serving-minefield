# Trap 122: 4-bit turboquant KV + MTP speculative decoding silently corrupts every completion on a build where either works alone

**Found by ayayalar (A Y).**

**Status: contributor-measured, conditions as reported.** Measured by the
contributor on their own hardware (single RTX 5090, vLLM 0.27.1, model
`unsloth/Qwen3.8-27B-NVFP4`); not yet independently reproduced by the registry.
The failure and its absence were both exercised multiple times in a control A/B
on the same build (one flag differs); broken and working flow are fully
described with command lines and raw responses in the contributions associated
with this entry. The working-state evidence is additionally reproducible from
the public [Qwen3.8-27B-NVFP4-TurboQuant](https://github.com/ayayalar/Qwen3.8-27B-NVFP4-TurboQuant) recipe.

**Symptom.** Serving Qwen3.8-27B-NVFP4 on one RTX 5090 with
`--kv-cache-dtype turboquant_4bit_nc` AND `--speculative-config
'{"method":"mtp","num_speculative_tokens":2}`, the server is fully up: `/v1/models`
responds, requests return HTTP 200, `finish_reason: stop` is normal, and nothing
is logged as an error. Yet every completion is garbage: `content` is empty, tool
calls never appear (`tool_calls: null`), needle-in-haystack retrieval fails, and
responses degenerate into repetition ("a a a a a a …", "think think think …").
It reads like a model-quality problem or a dead checkpoint, and it is neither:
the identical build with `--speculative-config` removed serves cleanly — tool
calls with correct JSON args, needle recall passing at 8K/64K/131K/196K, code-edit
passing. The interaction is not specific to the 4-bit KV dtype: under the same
FULL-graph capture the garble also reproduces with `fp8` KV on this lane. (The
earlier, pre-control fp8+MTP measurements that served clean were not under
FULL-graph capture — see Mechanism.)

**Mechanism (root-caused by the contributor on the same lane).** The observed
garble is a CUDA-graph capture artifact, not the KV dtype. On vLLM 0.27.1 at
capture-opt level >= 2 the default cudagraph mode is `FULL_AND_PIECEWISE`; the
static-MTP control (`--speculative-config '{"method":"mtp","num_speculative_tokens":2}'`,
no cudagraph override) captures in FULL mode. Under FULL capture the spec-verify
path inside `TurboQuantAttentionImpl.forward()` performs a GPU->CPU sync via
`query_start_loc.tolist()` and produces attention over the wrong chunk — draft
tokens are rejected on every step (`Accepted: 0`, `Per-position acceptance
rate: 0.000`) and long-context output collapses. The failure is binary in the
speculative flag exactly because the flag selects the graph mode. Same weights
+ same KV dtype without FULL-graph capture generate cleanly: stepping CUDA
graphs to PIECEWISE (via dynamic speculative decoding, see the fix) makes
MTP+turboquant fully correct on the identical build, with MTP accepting drafts.
This is the same drafter-and-graph-capture surface trap 62 already documents
(its 2026-07-28 addendum records full CUDA graphs corrupting/wedging a
speculative lane); the earlier hypothesis of quantized-KV numerics (failure
class of trap 62 by numerics rather than drafter config) was refuted by the
contributor's own single-variable result: the discriminator is the graph mode,
not the KV dtype — the garble also reproduced under FULL graphs with fp8 KV on
this lane.

**Stacks and builds bitten.** vLLM 0.27.1 on a single RTX 5090 (GB202, sm_120; 32
GiB, driver 610.43.02, CUDA 13.3), Python 3.13 venv with flashinfer and
nvidia-cutlass-dsl per unsloth's install guide, model = `unsloth/Qwen3.8-27B-NVFP4`
(compressed-tensors mixed NVFP4+fp8, Qwen3.5-family arch, native 262144 token
context). TurboQuant 4-bit KV explicitly selected as `turboquant_4bit_nc`.
The same weight+KV build with MTP off served clean (that is the control). The
fp8-KV MTP cell on this lane carries a caveat: it serves clean only outside
FULL-graph capture (see Symptom/Mechanism). One machine, one model build, one
vLLM build — version/quant/arch scoped.

**The check.** On any MTP + quantized-KV lane, before believing a quality probe:
run the two three-probe control sets, MTP flag on vs off on an otherwise
identical launch line: (a) a short chat prompt that must emit non-repeating
content, (b) one structured tool call that must return `tool_calls` with valid
JSON args, (c) a 4K needle-in-haystack that must return the marker. If any cell
in the MTP-on column is empty/garble and the MTP-off column is clean, this trap.
Five minutes, and it targets the cell trap 28's suggested matrix does not.

**The fix.** The verified working configuration keeps MTP on and removes the
FULL-graph capture: use dynamic speculative decoding
(`"num_speculative_tokens_per_batch_size": [[1,4,3]]` in the spec config), which
on vLLM 0.27.1 automatically steps cudagraphs from `FULL_AND_PIECEWISE` to
`PIECEWISE`, or pass `--enforce-eager` (costs ~28-40% decode on this build).
With PIECEWISE, MTP + turboquant 4-bit KV runs correct at the full 262K window
on the contributor's lane (tool calls 12/12, needles 8K-196K PASS, ~148.5
tok/s single-stream at the shipped default), so this is no longer an
operational either/or: MTP off with turboquant KV at full context and fp8 KV
with MTP on at <=227K remain fallbacks, and remaining single-variable ablations
(KV dtype sweep under MTP on) are closed — fp8 KV + MTP garbles under FULL
graphs just like 4-bit does, confirming the graph mode, not the KV dtype, is
the gate. The upstream fix attempt ([vllm PR
#40914](https://github.com/vllm-project/vllm/pull/40914), K+1 spec-verify
routing) targets the same class of bug but its dispatch predicate does not fire
on 0.27.1 (verified: 0/3508 calls eligible); the PIECEWISE/dynamic-SD route is
what actually fixes it on this version.

**Found.** 2026-08-14, while building and validating the public
[Qwen3.8-27B-NVFP4-TurboQuant](https://github.com/ayayalar/Qwen3.8-27B-NVFP4-TurboQuant)
serving recipe (262144-context, GPU-only) on powerspec hardware. The recipe repo
contains the still-runnable benchmark harness (tool-call + needle + code-edit,
stdlib-only) used for both the failing and working states.

**Attribution.** ayayalar (A Y); hardware qualification and raw A/B on their
lane, published as open-source recipe with reusable stdlib-only benchmark
scripts. Not reproduced by the registry (see status).
