# Traps by model

You are about to serve a specific model and want to know what has bitten
people on it. This is that page, and it is the page you add a row to when a
model bites you.

Two honest caveats. Absence from this table means nobody has reported on
that model here, not that it is safe. And many traps live in the stack, not
the model: everything in the stack-level table applies to whatever model you
serve on that stack.

## Model families

| Model family | Traps observed on it |
|---|---|
| Laguna S 2.1 (NVFP4, FP8, Q4_K_M, EXL3-tail builds) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [02](../traps/template/02-orphaned-think-close-tag.md), [03](../traps/reasoning/03-enable-thinking-default-drift.md), [04](../traps/template/04-history-reasoning-stripping.md), [06](../traps/reasoning/06-identity-sentence-eviction.md), [07](../traps/reasoning/07-reasoning-effort-silently-ignored.md), [11](../traps/runtime/11-speculative-depth-peak-and-collapse.md), [19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md), [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md) |
| Qwen 3.6 35B-A3B (NVFP4) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md) |
| Hy3-class ~295B MoE (community MXFP4 / NVFP4 compressed-tensors checkpoints) | [08](../traps/runtime/08-image-toolchain-newer-than-driver.md), [09](../traps/runtime/09-image-choice-changes-outcome.md), [10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) |
| MiniMax-M3 | [08](../traps/runtime/08-image-toolchain-newer-than-driver.md) |
| ~600B-class MoE with MTP drafter (community abliterated re-upload) | [14](../traps/versioning/14-finetune-reupload-not-drop-in.md) |

## Stack-level traps (apply to any model on that stack)

| Stack or layer | Traps |
|---|---|
| Eval harnesses and scorers | [05](../traps/evaluation/05-scorer-normalization-verdict-flip.md), [15](../traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md), [16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md), [17](../traps/evaluation/17-per-arm-recommended-sampling-confound.md) |
| Unified-memory boxes (DGX Spark, Strix Halo, Apple silicon class) | [13](../traps/memory/13-utilization-fraction-on-unified-memory.md) |
| Container images over mismatched drivers | [08](../traps/runtime/08-image-toolchain-newer-than-driver.md), [09](../traps/runtime/09-image-choice-changes-outcome.md) |
| llama.cpp attention and serve flags | [18](../traps/runtime/18-flash-attention-off-halves-deep-decode.md), [19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md) |
| Reasoning-model serving generally (fields, templates, budgets) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [04](../traps/template/04-history-reasoning-stripping.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md), [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md) |

## Adding a model

One row, linking the traps observed on it, in the PR that adds or extends
the entry. If you hit a trap on a model not listed here, that fact alone is
worth an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml):
"known trap, new model family" extends an entry's "Stacks and builds bitten"
section and gets you credited.
