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
| Laguna S 2.1 (NVFP4, FP8, Q4_K_M, EXL3-tail builds) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [02](../traps/template/02-orphaned-think-close-tag.md), [03](../traps/reasoning/03-enable-thinking-default-drift.md), [04](../traps/template/04-history-reasoning-stripping.md), [06](../traps/reasoning/06-identity-sentence-eviction.md), [07](../traps/reasoning/07-reasoning-effort-silently-ignored.md), [11](../traps/runtime/11-speculative-depth-peak-and-collapse.md), [19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md), [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md), [30](../traps/template/30-default-system-message-silently-replaced.md) |
| Qwen 3.6 35B-A3B (NVFP4) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md), [23](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md), [26](../traps/tools/26-tool-call-inside-unclosed-think.md) |
| Qwen 3.5 9B (Q4_K_M, llama.cpp) | [21](../traps/versioning/21-no-generation-config-server-defaults-win.md), [22](../traps/evaluation/22-family-card-budget-floors-differ-by-size.md) |
| Qwen 3.6 27B (Q4_K_M, llama.cpp) | [22](../traps/evaluation/22-family-card-budget-floors-differ-by-size.md), [29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md); control case in [21](../traps/versioning/21-no-generation-config-server-defaults-win.md) |
| Qwen 3.5 / 3.6 family broadly (dense, A3B MoE, Next hybrids; upstream reports) | [23](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md), [24](../traps/template/24-official-template-breaks-cpp-jinja.md), [25](../traps/template/25-empty-think-blocks-poison-prefix-cache.md), [26](../traps/tools/26-tool-call-inside-unclosed-think.md), [27](../traps/quantization/27-nvfp4-accuracy-cliff-config-misses.md) |
| DeepSeek V4-Flash (MTP builds; upstream reports) | [28](../traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md) |
| Hy3-class ~295B MoE (community MXFP4 / NVFP4 compressed-tensors checkpoints) | [08](../traps/runtime/08-image-toolchain-newer-than-driver.md), [09](../traps/runtime/09-image-choice-changes-outcome.md), [10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) |
| MiniMax-M3 | [08](../traps/runtime/08-image-toolchain-newer-than-driver.md) |
| ~600B-class MoE with MTP drafter (community abliterated re-upload) | [14](../traps/versioning/14-finetune-reupload-not-drop-in.md) |
| Ternary-Bonsai-27B (MLX 2bit, stock mlx_lm server, Apple silicon) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [03](../traps/reasoning/03-enable-thinking-default-drift.md), [07](../traps/reasoning/07-reasoning-effort-silently-ignored.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md), [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md), [29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) |

## Stack-level traps (apply to any model on that stack)

| Stack or layer | Traps |
|---|---|
| Eval harnesses and scorers | [05](../traps/evaluation/05-scorer-normalization-verdict-flip.md), [15](../traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md), [16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md), [17](../traps/evaluation/17-per-arm-recommended-sampling-confound.md), [31](../traps/evaluation/31-leftover-oracle-reranker.md) |
| Unified-memory boxes (DGX Spark, Strix Halo, Apple silicon class) | [13](../traps/memory/13-utilization-fraction-on-unified-memory.md) |
| Container images over mismatched drivers | [08](../traps/runtime/08-image-toolchain-newer-than-driver.md), [09](../traps/runtime/09-image-choice-changes-outcome.md) |
| llama.cpp attention and serve flags | [18](../traps/runtime/18-flash-attention-off-halves-deep-decode.md), [19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md) |
| mlx_lm server (fields, launch-flag defaults, unvalidated request body) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [03](../traps/reasoning/03-enable-thinking-default-drift.md), [07](../traps/reasoning/07-reasoning-effort-silently-ignored.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md), [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md), [29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) |
| Reasoning-model serving generally (fields, templates, budgets) | [01](../traps/reasoning/01-reasoning-field-two-names.md), [04](../traps/template/04-history-reasoning-stripping.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md), [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md) |

## Clean preflights

Models that passed the registry preflight on a named stack with no trap
observed. A clean bill is information too; absence from the trap tables
above plus presence here means "checked, nothing found", not "untested".

| Model and stack | Date | What was checked |
|---|---|---|
| Ternary-Bonsai-27B MLX 2bit on mlx server (Apple silicon) | 2026-07-27 | Sane completions, no stray or unbalanced think tags, structured tool_calls work (correct name and arguments). A deeper same-day pass then found real trap coverage on this lane (see the model row above); the clean verdicts here remain true for what this preflight checked |

## Adding a model

One row, linking the traps observed on it, in the PR that adds or extends
the entry. If you hit a trap on a model not listed here, that fact alone is
worth an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml):
"known trap, new model family" extends an entry's "Stacks and builds bitten"
section and gets you credited.
