# Trap 03: `enable_thinking` default drifts between revisions

**Found by Blackwellboy and TheTom.**

**Status: reproduced here**, reconciled across three independently run stacks.

**Symptom.** Two testers say "same model" and get materially different
behavior, then spend a week reconciling numbers that were never comparable.
Bug reports land against the model that are really config drift.

**Mechanism.** The same model family ships templates whose default for the
thinking kwarg differs by revision and by upload. One checkpoint defaults it
to `true`; another tester's pin documents `false`. Separately, some servers
supply the kwarg themselves, so the template's `| default(...)` branch never
runs and **omitting the kwarg is not the same as passing its default**. On
one llama.cpp path, absent renders byte-identical to `true`; on a vLLM path
with a different revision, absent lands wherever the template default points.

**Stacks and builds bitten.** Laguna S 2.1 across three independently run
stacks (vLLM/NVFP4, llama.cpp/Q4_K_M, and an EXL3-tail container). Revision
`0761412` (NVFP4 upload) defaults `enable_thinking` to `true`; another pinned
fork documented `false`. Reconciling the three stacks took days and produced the
corrected kwarg model now documented upstream: explicit `false` is the one
structural off-switch, explicit `true` fires, and which arm "absent" lands in
is revision-dependent and server-dependent.

The landing map for an absent thinking kwarg, measured across lanes
(2026-07-27 sweep): Laguna rev 0761412 templates default it ON (both vLLM
lanes); Qwen3.6-27B and Qwen3.5-9B on llama.cpp landed OFF (absent produced
no reasoning while explicit true fired, b9193/b9066); and on a llama.cpp
Laguna path the server supplies the kwarg so absent renders identical to
true (per the upstream #5 correction). Same request, three different arms,
depending on family, revision, and server. Send it explicitly, always.

**The server-supplies-the-kwarg arm, MLX spelling (mlx_lm server, confirmed
2026-07-27).** mlx_lm injects template kwargs server-side via a launch flag:

    --chat-template-args {"enable_thinking":false}

On the measured lane (stock mlx_lm serving prism-ml
Ternary-Bonsai-27B-mlx-2bit, Apple silicon), the shipped template turns
thinking off only on an EXPLICIT false (`enable_thinking is defined and
enable_thinking is false`), so the server flag lands the off arm for every
request that says nothing. Measured toggle map: explicit-on fired (516 chars
of reasoning), explicit-off did not fire, absent lands off-like. On this
lane "absent" equals the server flag, NOT the template default; the same
request replayed against a server launched without the flag would land the
template's other arm. That is exactly this trap's reconciliation hazard,
with the mechanism visible in the process line. Detection: read the launch
line for `--chat-template-args`, then send the three-arm toggle probe.

**The check.** Never reason about thinking from a template's default. Render
your own prompt through the serving path and confirm which branch you landed
in. Record the checkpoint revision hash next to every published number.

**The fix.** Send the kwarg **explicitly** on every request, both in
production and in every measurement arm. Pin the revision and state it.

**Found.** 2026-07-25 to 2026-07-26, reconciling three independent stacks.

**Attribution.** Blackwellboy, TheTom, and the offlabel issue threads where
the kwarg model was corrected. Context:
[laguna-s21-lab README](https://github.com/Blackwellboy/laguna-s21-lab#cross-validation--related-work).

## Added 2026-08-15: Qwen3.8 NVFP4 — unset effort defaults to explicit **xhigh** (independent first-party)

**Independently reproduced here by Blackwellboy** on
`RadixArk/Qwen3.8-27B-NVFP4` revision
`52d1adc5f38aa5ebf099c29ed7025ba34cfbb854`, template SHA256
`c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041`,
served under SGLang `lmsysorg/sglang:qwen38-27b` with a proven 262144-context
profile.

When `enable_thinking` is undefined **or** true, this template executes:

```jinja
{%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}
```

and injects the **xhigh** system instruction. Leaving `reasoning_effort`
unset is therefore **not** a neutral “model default” arm: it is byte-identical
to explicitly requesting `xhigh`.

Measured render hashes for the same user message
(`Return only the number 42.`):

| arm | SHA256 of rendered prompt |
|---|---|
| thinking unset / effort unset | `d5c052a8fbbe2495645582fca6230bd3e33ec41e161252d2cc61eefd0db31603` |
| thinking true / effort unset | same |
| thinking true / effort xhigh | same |

Public offline check (no GPU):
[`checks/reproduce_qwen38_reasoning_config_traps.py`](../../checks/reproduce_qwen38_reasoning_config_traps.py)
with fixture
[`checks/fixtures/qwen38_nvfp4_52d1adc/`](../../checks/fixtures/qwen38_nvfp4_52d1adc/).

Prior public lead / report: TheTom/offlabel. This addendum is an independent
Blackwellboy reproduction on a pinned local artifact, not a first-discovery
claim.

*Status of this addendum: reproduced here (runnable public template check).*

## Added 2026-08-30: GLM-5.3 Flash EXL3 K2 — absent control lands ON and unset effort lands MAX

**First-party Blackwellboy measurement** on `vcruz305/GLM-5.3-Flash-EXL3-K2`
revision `8b5d34f00c876027d737525d16c0e7439ca389d2`, Victor recipe commit
`832c3bd439fb7e40bed4955b73455afabbb90eeb`, served on a single DGX Spark /
GB10 through the pinned Victor vLLM/ExLlamaV3 runtime.

On this pin, omitting `enable_thinking` is again not neutral: the template
lands thinking ON. Explicit `enable_thinking:false` is the off arm. When
thinking is enabled, omitted `reasoning_effort` resolves to MAX; an invalid
`medium` value also resolves to MAX.

LOW/HIGH/MAX rendered to three distinct prompt hashes, so this is also a
negative control for Trap 07 rather than an accepted-but-ignored parameter:

| effort | rendered prompt SHA256 |
|---|---|
| low | `fa73d9a94cb0d52e1db244a78699ee12172173fea7c6d7df9e8961f5b32cbb82` |
| high | `bdcd945690ea721de18799a207c3243c8345ea1b856e40084020003cbdd13ba7` |
| max | `9a12aaef394d5a75bb28dc5cdb62bf6da4e3ad84b0900f5a71713b8d9fddc7cf` |

The bounded preflight used 42, 48 and 347 reasoning tokens for LOW, HIGH and
MAX respectively. The full disposition, including the matched-budget Sixcat
result and the Trap 12 corollary, is in
private evidence archive *(private evidence archived)*.

The rule remains the same: **send the thinking kwarg explicitly, and record
what omitted effort means on the exact template revision.**

*Status of this addendum: measured here; raw retained privately, with the
render/template behavior independently inspectable from the pinned public
artifact.*
