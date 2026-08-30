# GLM-5.3 thinking-level matrix — Minefield disposition

**Date:** 2026-08-30

This note preserves the Minefield-relevant results from a first-party GLM-5.3 Flash EXL3 K2 thinking-control matrix on a single DGX Spark / GB10. Raw request/response rows are retained privately; this public note contains only scrubbed system identity, aggregate measurements and the exact claim boundaries needed by the registry.

No new canonical trap number is created by this note.

## Unit under test

- Model: `vcruz305/GLM-5.3-Flash-EXL3-K2`
- Model revision: `8b5d34f00c876027d737525d16c0e7439ca389d2`
- Victor recipe commit: `832c3bd439fb7e40bed4955b73455afabbb90eeb`
- Victor prebuilt runtime revision: `e5fe5d84b64edb0b071f5715bfd915cd01792087`
- vLLM commit: `878631b6079d2cf9fb80830ef9cb41b43aded098`
- ExLlamaV3 commit: `17bc3923259ffd48aab742edd261a0ca45d55459`
- FlashInfer: `0.6.18rc10`
- Hardware: single NVIDIA DGX Spark / GB10
- TP=1
- fused EXL3 MoE
- native MTP `k=2`
- serving context: 65,536
- matrix benchmark protocol: Sixcat 0.5.0, strict, N=120 per arm

The model artifact was held fixed across the matrix.

## 1. Trap 03 extension: absent thinking control lands ON on this pin

The pinned Victor-patched GLM-5.3 template makes the absent control non-neutral:

- when neither `thinking` nor `enable_thinking` is defined, thinking is enabled;
- `enable_thinking:false` is the explicit off arm;
- with thinking enabled and no valid effort level supplied, the template resolves effort to `max`.

The preflight rendered LOW, HIGH and MAX to three distinct prompt hashes:

| effort | rendered prompt SHA256 |
|---|---|
| low | `fa73d9a94cb0d52e1db244a78699ee12172173fea7c6d7df9e8961f5b32cbb82` |
| high | `bdcd945690ea721de18799a207c3243c8345ea1b856e40084020003cbdd13ba7` |
| max | `9a12aaef394d5a75bb28dc5cdb62bf6da4e3ad84b0900f5a71713b8d9fddc7cf` |

`reasoning_effort` omitted rendered like MAX. An invalid `medium` value also rendered like MAX. Explicit thinking-off produced zero reasoning tokens in the frozen off protocol.

**Disposition:** addendum to [Trap 03](../traps/reasoning/03-enable-thinking-default-drift.md), not a new trap. The practical rule is unchanged: never publish a thinking arm whose request omitted the control and then call it a neutral/default arm.

## 2. Trap 07 negative control: effort is NOT ignored on this runtime/template

This matrix was also a direct probe of [Trap 07](../traps/reasoning/07-reasoning-effort-silently-ignored.md).

LOW/HIGH/MAX produced distinct rendered prompt hashes and different reasoning usage on the same bounded preflight prompt:

- LOW reasoning tokens: 42
- HIGH reasoning tokens: 48
- MAX reasoning tokens: 347

The accepted-but-ignored failure mode therefore did **not** reproduce on this pinned GLM-5.3 K2 stack.

The fallback behavior also matched the inspected template:

- unset effort == MAX: **YES**
- invalid `medium` == MAX: **YES**

**Disposition:** negative/control result only. Do not add a Trap 07 reproduction for this stack.

## 3. Trap 12 corollary: effort level and output budget interact

The full matched Sixcat matrix returned:

| arm | score |
|---|---:|
| OFF | 74.2 |
| LOW | 75.8 |
| HIGH | 76.7 |
| MAX | 44.2 |

The MAX result is **not** evidence that maximum reasoning effort is intrinsically lower quality. Under the same strict output budgets used by the other arms, MAX generated enough reasoning that many responses truncated before the answer completed.

Paired HIGH -> MAX movement:

- to pass: 2
- to fail: 41
- net: -39 items
- score delta: -32.50 points

This is the same measurement class as [Trap 12](../traps/evaluation/12-empty-content-at-token-ceiling.md): the evaluation can become a test of whether the answer fits after reasoning rather than a clean capability comparison. Here the new variable is the requested **reasoning-effort level** while the benchmark budget is held fixed.

**Disposition:** Trap 12 corollary / matrix finding. No new trap number. Any public LOW/HIGH/MAX comparison must put the output budget and truncation counts next to the score.

## 4. Trap 29 additional first-party stack: client/UI off is not template off

A separate first-party GLM-5.3 NVFP4/vLLM serving path reproduced the control-plane half of [Trap 29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md).

On that path the controller was configured with reasoning disabled in its own UI/client settings and the server had a reasoning parser, but the request omitted `chat_template_kwargs.enable_thinking`. The template defaulted thinking ON anyway.

A direct same-prompt control measured:

| request arm | completion tokens | reasoning length | visible answer |
|---|---:|---:|---|
| no template kwarg | 34 | 107 | correct |
| `enable_thinking:false` | 7 | 0 | correct |
| `enable_thinking:true` | 34 | 107 | correct |

The corrected controller path then put `chat_template_kwargs.enable_thinking:false` on the wire and the hidden-reasoning pathology disappeared without a model-server restart.

**Disposition:** addendum to Trap 29. A UI/client setting that hides or disables reasoning presentation, and a server `--reasoning-parser`, are not evidence that the chat template stopped generating reasoning.

*Status of this addendum: measured here, raw retained privately.*

## 5. Candidates preserved but NOT promoted by this note

### Prefix-cache probes smaller than the cache block quantum

On another first-party GLM-5.3 path, short requests could report zero prefix-cache hits while a long shared-prefix probe produced a large positive hit count and roughly halved wall time. The relevant cache block size on that path was 7,168 tokens.

The Victor K2 runtime in this matrix reports a different block quantum (8,704), so the 7,168 figure must not be copied onto it.

**Status:** candidate/intake. Related to the prefix-cache family, but distinct from Trap 129's grouped-KV minimum-hit mechanism. Needs a bounded cross-stack probe before promotion.

### Victor long-context K-pool fault

Victor Cruz's public recipe at commit `832c3bd` reports that a 131,072 `max_model_len` can allocate while a prompt around 98K can CUDA-fault in sparse-MLA K-pool tail seeding.

**Attribution:** `@vcruz305` / Victor Cruz.

**Status:** public-source, not reproduced by this matrix. Do not describe as first-party Minefield reproduction.

### Victor DFlash page-transition fault

The same public recipe reports a DFlash + FlashAttention path that can pass short requests and then fault at the first cache-page transition, while the Triton attention backend crosses that boundary.

**Attribution:** `@vcruz305` / Victor Cruz.

**Status:** public-source, not reproduced by this matrix. No DFlash arm was run here.

## Publication rule from this matrix

For reasoning-level comparisons, record all of these together:

1. exact template/runtime/model revision;
2. explicit thinking on/off kwarg;
3. explicit reasoning-effort value;
4. rendered-prompt proof or hash;
5. output-token ceiling;
6. reasoning-token use;
7. truncation count;
8. paired item flips.

A score without those fields can turn a reasoning-budget artifact into a model-quality claim.