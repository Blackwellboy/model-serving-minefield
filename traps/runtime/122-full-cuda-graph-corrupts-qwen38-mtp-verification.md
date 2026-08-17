# Trap 122: FULL CUDA-graph capture silently corrupts Qwen3.8 MTP verification on vLLM 0.27.1

**Found by ayayalar (A Y).**

**Status: contributor-measured, conditions as reported.** Measured by the
contributor on a single RTX 5090 with vLLM 0.27.1 and
`unsloth/Qwen3.8-27B-NVFP4`; not independently reproduced by the registry. The
failure and working controls were exercised repeatedly on the contributor's
lane. The working recipe and reusable benchmark harness are public in
[Qwen3.8-27B-NVFP4-TurboQuant](https://github.com/ayayalar/Qwen3.8-27B-NVFP4-TurboQuant).

**Symptom.** The server is fully ready, `/v1/models` responds, requests return
HTTP 200 with normal `finish_reason: stop`, and no serving error is logged, yet
MTP generations collapse into empty `content`, missing tool calls, failed needle
recall, or repetitive text such as `a a a ...` / `think think think ...`. The
failure was first isolated while using `turboquant_4bit_nc` KV, but a later
control reproduced the same collapse with `fp8` KV under the same FULL CUDA-graph
capture. That refutes the original hypothesis that 4-bit KV itself is the gate.

**Mechanism (root-caused on the contributor's lane).** On vLLM 0.27.1 at
capture-opt level >= 2, the default CUDA-graph mode is `FULL_AND_PIECEWISE`.
With a static MTP configuration, the affected speculative-verification path is
captured in FULL mode. On the contributor's measured path,
`TurboQuantAttentionImpl.forward()` performs a GPU-to-CPU synchronization via
`query_start_loc.tolist()` during spec verify; under FULL capture the attention
chunk is wrong, draft tokens are rejected on every step (`Accepted: 0`,
per-position acceptance `0.000`), and output collapses while transport still
looks healthy. Switching the same serving build to PIECEWISE graph capture
restores correct generation and non-zero draft acceptance.

The contributor also reproduced the output-collapse signature with `fp8` KV
under FULL capture. That is strong evidence that **graph mode, not 4-bit KV
dtype, is the discriminator on this lane**. It does not establish that every KV
dtype reaches the identical internal line on every vLLM build, so keep the
mechanism scoped to these measured conditions rather than generalising it to all
MTP or all CUDA-graph implementations.

**Stacks and builds bitten.** vLLM 0.27.1; single RTX 5090 (GB202/sm_120, 32
GiB; driver 610.43.02; CUDA 13.3); Python 3.13 environment with FlashInfer and
nvidia-cutlass-dsl; `unsloth/Qwen3.8-27B-NVFP4` (compressed-tensors mixed
NVFP4+fp8, Qwen3.5-family runtime architecture, native 262144-token context).
The original failing cell used `turboquant_4bit_nc` KV. A separate `fp8`-KV FULL
capture control showed the same corruption signature. Version, model, hardware,
and graph-mode scope matter.

**The check.** Do not diagnose this trap from MTP-on versus MTP-off alone; that
only proves that speculation changes the outcome. Run a three-arm control on the
same model, runtime build, KV dtype, request, sampling settings, and memory
configuration:

1. **FULL cell:** static MTP under the vLLM 0.27.1 default
   `FULL_AND_PIECEWISE` mode. Record graph-mode startup output and MTP acceptance
   counters.
2. **PIECEWISE cell:** keep MTP enabled but add dynamic speculative decoding,
   e.g. `"num_speculative_tokens_per_batch_size": [[1,4,3]]`, so vLLM steps
   FULL capture down to PIECEWISE. Confirm that downgrade in the startup log.
3. **No-spec control:** same launch with MTP disabled.

For each arm run at least: one short non-repetition prompt, one structured tool
call whose name and JSON arguments are checked, and one needle-recall prompt.
This trap is supported when the FULL cell corrupts while PIECEWISE and no-spec
controls are clean, with the graph-mode transition actually observed. If FULL
and PIECEWISE both fail, or the graph mode was not verified, the result is
inconclusive for Trap 122.

**The fix.** On this vLLM 0.27.1 lane, keep MTP but prevent FULL capture of the
affected verify path. The contributor's verified route is dynamic speculative
decoding (`"num_speculative_tokens_per_batch_size": [[1,4,3]]`), which makes
vLLM downgrade to PIECEWISE for reliability. `--enforce-eager` is a slower
fallback that also avoids FULL capture. Under the PIECEWISE route the
contributor reports full-window correctness on the same RTX 5090: tools 12/12,
needles 8K through 196K PASS, code-edit PASS, and about 148.5 tok/s
single-stream under the published default. Those are working-state measurements
for this exact recipe, not a general vLLM performance claim.

**Related boundaries.** [Trap 28](28-mtp-fails-only-under-concurrency-or-temperature.md)
owns speculative paths that look green in the single-stream/greedy cell and then
fail under concurrency, temperature, or layout. Trap 122 is deliberately
different: its broken cell is already single-stream and can be discriminated by
FULL versus PIECEWISE graph mode. [Trap 62](62-spec-decode-garble-under-wrong-drafter-config.md)
contains an older DeepSeek/DGX-Spark report that full CUDA graphs can wedge
speculative decode, but that report was not isolated there. Trap 122 is the
scoped contributor-measured Qwen3.8/vLLM 0.27.1 graph-mode A/B; it does not
retroactively upgrade Trap 62's older evidence.

**Found.** 2026-08-14; graph-mode discriminator/root-cause controls completed
2026-08-15/17 while validating the public Qwen3.8 RTX 5090 recipe.

**Attribution.** ayayalar (A Y): discovery, RTX 5090 hardware qualification,
FULL-versus-PIECEWISE controls, FP8-vs-4-bit discriminator, raw serving A/B, and
public reproduction recipe/benchmark harness. Minefield maintainer adjudication
only narrows the canonical title, confirmation check, and evidence boundary; it
does not claim Blackwellboy reproduced the contributor's hardware result.
