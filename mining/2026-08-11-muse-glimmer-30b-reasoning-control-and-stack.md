# Muse Glimmer 30B (llama.cpp + DFlash): reasoning-control render, ops latency, and stack confirmations

**Date:** 2026-08-11  
**Status:** measured here, raw not published. Bounded single-GPU campaign on a pinned Unsloth GGUF + DFlash pair. **No new trap number.** Mechanisms that already have owners are recorded as corroborations/extensions on those entries; this note holds the render story, the full-suite coding null, and claim boundaries that must not become traps.

**Model / stack (public-safe pins):**

| Field | Value |
|---|---|
| Weights | `unsloth/Muse-Glimmer-30B-GGUF` rev `988969716071c538d862a7c10a2419caaafe4d9b` |
| Quant | UD-Q4_K_XL (+ DFlash draft for primary arms) |
| GGUF SHA256 | `82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38` |
| DFlash SHA256 | `27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc` |
| Runtime | llama.cpp `62bf73d25c53b8161f8a22894d4f90c4aebbd7d0` |
| Template SHA256 | `114f55ebdc1804c1af371197b9fdf2d6bb925966c9dfe46b73782a71bc07965e` |
| Hardware class | single consumer Blackwell GPU |
| Eval harness | EvalPlus 0.3.1; HumanEval+ 164 + MBPP+ 378 |

## What was proven at the render layer

The distributed template defaults `reasoning_strength` to **high** when the Jinja variable is unset. Card-style system text `Reasoning strength: low` does **not** bind that variable. Under a clean server (no server-level kwargs injection):

| Arm | How control was applied | Rendered directive(s) |
|---|---|---|
| Bare default | no kwargs | single **HIGH** |
| Card method | system text only | **LOW then HIGH** (double directive) |
| Kwargs low | `chat_template_kwargs.reasoning_strength=low` | single **LOW** |
| Kwargs high | `chat_template_kwargs.reasoning_strength=high` | single **HIGH**, **byte-identical** to bare |

**Not Trap 113.** Trap [113](../traps/template/113-inline-system-role-is-not-a-stable-contract.md) is about *inline system-role placement* in a multi-message sequence. This finding is *documented control text that never becomes a template kwarg*, while the template's own default still fires. Same operator lesson as other dead-control work: **inspect the final rendered prompt**, do not trust card prose or HTTP 200.

Related owners for accepted-but-inert knobs on the same pin:

- `enable_thinking=false` - dead template kwarg → [trap 77](../traps/reasoning/77-only-one-request-field-is-validated.md) / [trap 03](../traps/reasoning/03-enable-thinking-default-drift.md)
- `reasoning_effort` low/high - unread on this path; server only special-cases `"none"` → [trap 07](../traps/reasoning/07-reasoning-effort-silently-ignored.md)

## Full-suite coding: double directive did not move pass@1

Paired EvalPlus on the same greedy + DFlash serve, **content-only** extraction (never execute `reasoning_content`):

| Arm | Combined Plus | Empty final | Median reasoning chars | Median wall |
|---|---|---|---|---|
| M2 card low (LOW+HIGH) | **82.10%** | ~0.74% | 1060 | 1.87 s |
| M3 kwargs low (clean LOW) | **81.92%** | ~0.37% | 460.5 | 1.24 s |

Paired n=542: BOTH_PASS=435, BOTH_FAIL=88, M2_only=10, M3_only=9, McNemar **p=1.0**.

**Supported claim:** template double-directive is real; **measured coding cost of the double directive is NOT demonstrated** on this suite.

**Supported operational claim (same suite only):** clean kwargs-low reduced median reasoning length by about **57%** and median wall time by about **34%** without a material Plus change.

**Do not claim:** "clean low improves coding quality."

Every real row (1368) preserved full request body and render SHA.

## Tight budget slice (secondary only)

At `max_tokens=512`, n=30: card-low empty 3/30 Plus 70%; kwargs-low empty 1/30 Plus 86.7%. At 1024 the direction did not hold. This is **trap [12](../traps/evaluation/12-empty-content-at-token-ceiling.md)** territory (reasoning can consume the ceiling), not a general quality ranking.

## Speculative decoding (DFlash)

Bounded 40-task greedy battery (separate R2 pass): quality 39/40 both ON and OFF, pass/fail agreement 40/40, exact content match **36/40**. Score parity is not text identity. Workload matrix showed draft acceptance tracking decode speed nearly linearly (Pearson ≈ 0.998 on the measured matrix). Owner: [trap 111](../traps/evaluation/111-greedy-spec-decode-medians-are-a-content-lottery.md).

## Harness / API / context (owners only)

| Observation | Owner |
|---|---|
| Single-turn sequential-tool score 1/4 vs multi-turn tool-result loop 29/30 | [trap 42](../traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md) |
| Forced named `tool_choice` ignored; `required`/`auto` effective on tested path | [trap 78](../traps/tools/78-tool-choice-accepted-and-ignored.md) |
| No `generation_config.json` in pin → server defaults | [trap 21](../traps/versioning/21-no-generation-config-server-defaults-win.md) |
| Needle retrieval OK at **126079** prompt tokens under n_ctx=131072; distant two-fact synthesis failed near limit | [trap 55](../traps/evaluation/55-supported-context-is-not-trained-context.md) / [trap 61](../traps/evaluation/61-advertised-window-fails-silently.md) class |
| Streaming material under `reasoning_content` only → content-only client blank | [trap 23](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md) class |

## Practical Qwen3.6-27B lane (not a model-quality A/B)

Same host class, HumanEval+ only, greedy: Qwen3.6-27B Q4_K_M with MTP reasoning-off scored HE+ **92.1%**; Muse kwargs-low HE+ **91.5%**. Different model, quant, template, reasoning policy, runtime, and speculative path. **Not a trap. Not a ranking.**

## Claim boundaries (explicit)

- Do not allocate a new trap for "card text does not set reasoning strength."
- Do not treat tiny M1/M4 score spreads under DFlash/greedy as semantic differences when renders are byte-identical.
- Do not promote Q4 vs Q5 39/40 both-pass as universal quant parity.
- Do not treat aggregate concurrency throughput alone as "faster for agents" without per-request latency.
- Multimodal capability was **not** tested (no vision projector in the pin).

## Update 2026-08-12: offlabel cross-check + bounded RTX 5090 follow-up

Tom Turney's public [offlabel Muse Glimmer 30B guide](https://github.com/TheTom/offlabel/blob/main/models/muse-glimmer-30b.md) landed on 2026-08-11 after a separate release-day behavioral/serving battery. Treat it as **external evidence with its own scope** (GB10 for most serving work, different quant, single tester), not as a replacement for the measurements above.

### What independently lined up

- The shipped template/control story matched: absent `reasoning_strength` resolves high; card-style system LOW leaves a contradictory LOW+HIGH render; `chat_template_kwargs.reasoning_strength` is the effective lever. offlabel also reports `enable_thinking` and top-level `reasoning_effort` inert on its path. For the dead-knob observation, offlabel explicitly credits Blackwellboy's same-day report, so this is **independent execution, not clean independent discovery**.
- offlabel's DFlash story is workload-sensitive in the same direction as our 48-prompt acceptance matrix. Our matrix is the quantitative owner here; the external result is corroboration, not a new speed constant.
- offlabel also found greedy DFlash output non-identity. Different hardware/quant means the exact rates are not directly comparable.

### Bounded RTX 5090 reproduction of the new operator gotchas

A follow-up on our pinned RTX 5090 lane tested four short sequential serve arms on 8 representative prompts:

| Arm | Configuration | Mean wall | Draft counters | Exact vs target-only arm |
|---|---|---:|---|---:|
| A | target only | 1.065 s | none | - |
| B | `--model-draft` only | 1.039 s | none | 6/8 |
| C | `draft-dflash`, n_max=3 | 0.748 s | present | 6/8 |
| D | `draft-dflash`, n_max=15 | 0.640 s | present | 5/8 |

**Measured operator lesson:** a drafter can log as loaded without speculative decoding being active. On this build, the `--model-draft`-only arm had no draft/acceptance counters and behaved like target-only, while explicit `--spec-type draft-dflash` produced counters and the expected latency reduction. Do not use "draft model loaded" as the proof of activation; verify the speculative implementation and live counters.

This does **not** invalidate the earlier Muse DFlash measurements: those stored runs used `draft-dflash`, n_max=15, and preserved draft/acceptance counters.

### Greedy identity: stronger boundary, still not a correctness claim

Before comparing DFlash, the target-only path was repeated three times on 12 prompts; **10/12** were byte-identical across all three repetitions. In the bounded A-vs-D comparison, only **5/8** outputs were exact matches.

That supports the existing [trap 111](../traps/evaluation/111-greedy-spec-decode-medians-are-a-content-lottery.md) boundary that task/quality parity is not text identity. It does **not** establish a DFlash correctness defect: the target-only path itself was not perfectly reproducible, and the 8-prompt follow-up was not a graded semantic suite.

### Agent harness: correct tool call can still end in a wrong final

A 20-task deterministic tool-result fidelity battery produced **20/20 correct tool calls** but **2/20 final summaries that did not match the tool result**. There were **0** cases where the final simply substituted the value the user originally expected; the two misses were final-answer fidelity failures, not tool-selection failures.

Practical harness rule: score the user-facing final answer against the actual tool result. `tool_call_correct=true` is not enough to prove the task completed correctly.

### Behavioral cross-checks that should stay model notes, not serving traps

- **Clean-code calibration corroborated:** Muse invented a defect in **0/12** clean snippets and accepted all 12 as correct. On a matched 12-bug set it found **8/12**. The positive result is specifically low false-defect rate; do not rewrite it as perfect bug detection.
- **Turn-2 refusal collapse did not cleanly reproduce here:** in a 12-scenario bounded reframe battery there were **0** strict `TURN1_HELD -> TURN2_FOLDED` transitions under the campaign scorer. Some cases moved to partial. offlabel's held-then-fold example remains valid for its battery; our result says not to generalize it as a guaranteed Muse behavior across prompts/stacks.

### Routing after the cross-check

- **No new public trap number.**
- `--model-draft` loaded != speculative decoding active: verified operator/llama.cpp stack candidate; keep as mining/stack guidance unless a distinct general mechanism clears the normal promotion bar.
- DFlash exact-text non-identity: existing trap 111 corroboration/claim boundary.
- Correct tool call != correct final summary: research-harness/playbook extension candidate, not evidence that native tool calling is broken.
- Clean-code false-defect result and refusal/reframe behavior: model characterization only.

*Status of 2026-08-12 update: measured here, raw not published. External offlabel claims remain attributed to their source and are not relabelled as Blackwellboy measurements.*

## Related entries updated in the same PR

Addenda on traps **07, 12, 21, 42, 77, 78, 111**; model index row; llama.cpp stack pointer; playbook note on content-only extract + render provenance.
