# 2026-08-25: matched OBLIT packing and runtime refusal-direction ablation

Status: **first-party evidence note; raw packets remain private**.

This note records two same-day experiments that materially sharpen existing
Minefield entries without creating new trap numbers.

## 1. Qwen3.8-27B OBLITERATED: packing, not abliteration, dominated the earlier speed gap

Private owning evidence:

- repo: `Blackwellboy/blackwellbench-lab`
- branch: `research/qwen38-abliterated-autoround-investigation-20260824`
- evidence commit: `1e43f3273daca8ebf7292bd161b64fbdeb0124f3`
- path: `research/qwen38-abliterated-autoround-investigation-20260824/optimization/`

The first OBLIT AutoRound candidate exported through `--format auto_gptq` and
identified as `quant_method=gptq` with `g_idx`. It ran through the GPTQ/Marlin
path and measured about 191.9 tok/s on the matched code cell.

Candidate D rebuilt the exact same OBLIT BF16 source into the packing identity
used by the fast Frozenlock reference: `auto_round:auto_gptq`, `g_idx=0`,
matched qweight inventory, matched MTP treatment and matched auxiliary-tensor
size.

Matched vLLM + DFlash2 K7 results:

| metric | Frozenlock normal | OBLIT Candidate D |
|---|---:|---:|
| code tok/s | 233.83 | 233.10 |
| code acceptance | 80.3% | 79.9% |
| prose tok/s K7 | 107.15 | 101.18 |
| prose acceptance K7 | 21.6% | 20.0% |
| finished-work sum mean wall | 2.49 s | 2.23 s |
| tiny intelligence smoke | 8/8 | 7/8 |

The OBLIT target reached 109.43 prose tok/s at K6. K7 remained the clear code
winner. The one intelligence-smoke miss was a strict tool-call format near-miss;
the experiment does not support a universal intelligence-equivalence claim.

**Disposition:** strong new first-party instance for
[`Trap 10`](../traps/quantization/10-quant-label-is-not-the-kernel-path.md).
The key failure mode is export/packing identity: two artifacts that can both be
described loosely as W4A16/group-128 AutoRound did not land on the same runtime
representation or speed class.

**Claim boundary:** this does not establish that abliteration has zero cost in
general. It establishes that the earlier ~18% route-level code gap in this
campaign was dominated by the unmatched export/packing path; after packing was
matched, code speed and speculative acceptance were effectively at the
reference level in this session.

## 2. DeepSeek-v4-Flash one-DGX-Spark: same weights and same image digest, runtime overlay changes refusal behavior

Private owning evidence:

- repo: `Blackwellboy/openclaw-workspace`
- evidence commit: `022d4dce39fe8fbbd37c587c7349a17683311283`
- path: `chatgpt-returns/mia-dsv4-runtime-ablate-20260824`
- upstream Mia pin: `bf162cce0ed8c0dfcba645f7addf60b07823550f`

Dexter2 kept the same EXL3 checkpoint bytes and the same pinned runtime image.
Mia's opt-in `ABLATE=1` path bind-mounted a model-code overlay and projected the
published refusal direction at runtime with:

- lambda: 3.5
- layers: 10-42
- direction SHA256:
  `6e4d8a8f3aa9e21795faab2c5b14d29b019acdf2ddbfbd8238430458a5837fe0`
- weights changed: no
- weights re-downloaded: no
- DSpark K: 5
- context: 384000 before and after

Matched behavior/performance:

| metric | stock | runtime ABLATE |
|---|---:|---:|
| refusals, thinking off | 8/8 | 0/8 |
| refusals, thinking on | 7/8 | 0/8 |
| capability smoke, thinking off | 6/6 | 6/6 |
| capability smoke, thinking on | 2/6 | 2/6 |
| code tok/s | 36.621 | 36.985 |
| prose tok/s | 21.841 | 22.812 |
| DSpark code acceptance | 0.5463 | 0.5477 |
| DSpark prose acceptance | 0.2568 | 0.2710 |

The thinking-on 2/6 result was the same empty-content-at-length/reasoning-budget
artifact on both arms, so the bounded smoke found no obvious capability
regression from the runtime projection. A 13,558-token retrieval sanity check
passed, and Hermes continued to reach the lane.

**Disposition:** supporting instance for
[`Trap 09`](../traps/runtime/09-image-choice-changes-outcome.md), specifically a
sharpening of its unit-under-test rule. An image digest by itself does not fully
identify a runtime when model code is replaced by a bind mount or overlay.
Record mounted code, injected files/config and compile/AOT cache identity as
part of the serving artifact.

This is **not** another instance of
[`Trap 14`](../traps/versioning/14-finetune-reupload-not-drop-in.md): there was
no finetuned/abliterated weight re-upload in this experiment. The weights stayed
unchanged; the behavioral intervention lived in the runtime path.

## Combined lesson

Both experiments are the same higher-level discipline from opposite sides:
**artifact identity must describe the code path that actually executes, not the
label humans use for it.**

- Quantization recipe labels can hide a different packed representation and
  loader/kernel path.
- Image digests can hide runtime-mounted model code that changes behavior with
  identical weights.

For publishable comparisons, record the full execution identity: checkpoint
revision and hashes, packing/export metadata, auxiliary-head treatment, image
digest, mounted overlays, runtime config and the backend actually selected.
