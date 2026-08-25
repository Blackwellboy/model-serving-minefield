# 2026-08-20 — jschmied Qwen3.8 fixed-template reconciliation

## Purpose

Review `jschmied/Qwen-Fixed-Chat-Templates` against Minefield's existing Qwen3.8-27B evidence. Preserve useful independent corroboration and runtime facts without treating the contributor's policy choices as native Qwen semantics or inventing new canonical traps where existing owners already fit.

Source reviewed:
- https://github.com/jschmied/Qwen-Fixed-Chat-Templates
- `README.md`
- `chat_template.jinja`
- `test_template.py`
- relevant commit history

Upstream runtime source cross-check:
- vLLM `v0.27.1` `ChatCompletionRequest`
- vLLM `v0.27.1` `vllm/v1/sample/thinking_budget_state.py`

## High-value findings retained

### 1. Independent corroboration: unset `reasoning_effort` can land on `xhigh`

jschmied reports the Unsloth Qwen3.8-27B NVFP4 template defaulting an unset reasoning-effort request to `xhigh`, and measured a hard coding request where the xhigh/default arm consumed the entire 26,000-token completion budget inside reasoning and returned zero content.

Minefield had already independently reproduced the template-control half of this mechanism on a different Qwen3.8 NVFP4 pin (`RadixArk/Qwen3.8-27B-NVFP4@52d1adc`) under SGLang: unset effort rendered byte-identically to explicit `xhigh`.

Disposition: **independent public corroboration / extension of Trap 03**, not a new trap.

Existing owner:
- `traps/reasoning/03-enable-thinking-default-drift.md`
- `mining/2026-08-15-qwen38-reasoning-config-traps.md`

Important scope boundary: jschmied's 26k/empty-content runtime result is his measured Unsloth/vLLM/GB10 lane. Minefield's first-party result proves the rendered-template control on a different pin; it does not claim the same 26k runtime outcome.

### 2. Independent corroboration: `medium` has no dedicated instruction branch on the original Qwen3.8 template shape

jschmied's base/template analysis agrees with Minefield's pinned Qwen3.8 fixture that `medium` is accepted but injects no dedicated effort instruction, while low/xhigh branches do inject instructions.

Disposition: **independent public corroboration / extension of Trap 07**, not a new trap.

Existing owner:
- `traps/reasoning/07-reasoning-effort-silently-ignored.md`

### 3. vLLM 0.27.1 really exposes sampler-enforced `thinking_token_budget`

This is source-confirmed in vLLM 0.27.1, not merely a README claim.

`ChatCompletionRequest` exposes:

- `reasoning_effort: none|minimal|low|medium|high|xhigh|max`
- `thinking_token_budget`

`vllm/v1/sample/thinking_budget_state.py` defines a `ThinkingBudgetStateHolder` whose stated job is to track thinking sections and force the end-of-thinking token sequence when the budget is exhausted. The implementation applies forcing at sample/logit time, so this is materially different from a prompt sentence asking the model to stop.

jschmied reports one Qwen3.8 GB10 A/B at xhigh:

- no explicit thinking budget: 97,708 reasoning characters, 0 content characters;
- `thinking_token_budget=1500`: 5,562 reasoning characters, 18,512 content characters.

Disposition: **useful public-source mitigation / future Qwen3.8 experimental arm**. The implementation fact is source-confirmed. The numeric A/B remains contributor-measured and is not a Blackwellboy reproduction.

Do not relabel old Minefield or Qwen3.8 benchmark arms retroactively. If tested, make it a new controlled variable with exact vLLM build, reasoning parser, effort level, max completion tokens and rendered prompt recorded.

### 4. JSON-string tool arguments match existing Trap 43

jschmied adds support for tool-call `function.arguments` arriving as a serialized JSON string instead of an object/mapping. This is the same template-dialect class already owned by:

- `traps/template/43-tool-args-string-not-mapping.md`

His patch keeps mapping arguments working and adds a string branch. That is useful corroboration of the class on a Qwen3.8-derived XML tool template, but does not warrant a new canonical number.

## Useful things not promoted as native semantics

### Custom `minimal`, `high` and `max` mapping

jschmied chooses a monotonic compatibility policy:

- `minimal -> low`
- `high -> a new custom high prompt`
- `max -> xhigh`

This is a reasonable serving-template policy, but it is **not evidence of native Qwen3.8 effort semantics**. In vLLM 0.27.1, `max` is documented as DeepSeek-V4-specific. His custom `high` instruction is explicitly unmeasured for quality/length ordering.

Any future benchmark using this template must name the template revision and must not publish its `high` arm as if it were stock Qwen3.8 `high`.

### Unknown effort -> `medium`

The template silently maps an unknown effort string to medium. That avoids accidental escalation to xhigh, but it also hides typos/config drift. From a Minefield measurement perspective, fail-loud validation is safer than silently changing the requested arm. Do not adopt this fallback into benchmark harnesses without an explicit policy decision.

### xhigh termination/concision wording

The added xhigh wording is a prompt-level nudge, not enforcement. jschmied correctly labels it unmeasured. Minefield should prefer the actual sampler-side budget arm when testing budget control on vLLM builds that support it.

## Important defects his current template still leaves in place

The current `chat_template.jinja` still contains the assistant-history branch equivalent to:

`preserve_thinking is undefined or preserve_thinking is true`

and still emits a `<think>...</think>` block around assistant history even when historical `reasoning_content` is empty.

Those match Minefield's independently reproduced Qwen3.8 findings:

- default/unset `preserve_thinking` replays prior reasoning: Trap 04 extension;
- content-only historical assistant turns can receive empty think blocks: Trap 25 extension.

Therefore this repository should not be described as fixing all known Minefield Qwen3.8 template hazards.

Existing owners:
- `traps/template/04-history-reasoning-stripping.md`
- `traps/template/25-empty-think-blocks-poison-prefix-cache.md`

## Revision warning

Minefield's pinned Qwen3.8 fixture and jschmied's Unsloth-derived base are not byte-identical template revisions. One observed difference is the handling of `high`: Minefield's `RadixArk@52d1adc` fixture raises on `high`, while jschmied reports the Unsloth base aliasing `high` upward to `xhigh` before his patch.

That is not a contradiction. It strengthens the existing rule: publish checkpoint revision + template hash + effective rendered prompt with any reasoning-effort result.

## Recommended bounded follow-up

If Qwen3.8 testing is reopened for a narrow research arm, the highest-value comparison is not "his template vs ours". It is:

1. same pinned Qwen3.8 checkpoint and vLLM 0.27.1-compatible runtime;
2. explicit `reasoning_effort=xhigh` in both arms;
3. arm A: no `thinking_token_budget`;
4. arm B: a fixed `thinking_token_budget` such as 1500;
5. same max-completion limit and sampling;
6. capture rendered prompt, reasoning tokens/chars, content tokens/chars, finish reason, answer correctness and wall time;
7. repeat on more than one task before making a quality claim.

Separately, an offline template render should verify whether the tested artifact still carries the `preserve_thinking` and empty-history-think behaviour before adopting any third-party replacement template wholesale.

## Attribution

- External repository / contributor measurements: `jschmied`
- Existing Minefield Qwen3.8 first-party reproduction: Blackwellboy
- Existing prior public lead referenced in Minefield: TheTom/offlabel

No new canonical trap allocated by this reconciliation.
