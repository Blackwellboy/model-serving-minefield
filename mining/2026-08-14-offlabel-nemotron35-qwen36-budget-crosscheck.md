# Offlabel 2026-08-12 cross-check: Nemotron 3.5 Lightning and Qwen3.6-27B

**Disposition: existing-trap corroboration, no new trap IDs.**

This note records the serving-path parts of two new/updated public guides in
[TheTom/offlabel](https://github.com/TheTom/offlabel). The behavioral-model
judgments in those guides are outside this registry's scope unless they expose
a serving, template, parser or measurement failure. Nothing here is relabelled
as Blackwellboy first-hand measurement.

## 1. NVIDIA Nemotron 3.5 Lightning 30B-A3B

Primary public guide:
[`models/nemotron-3.5-lightning-30b-a3b.md`](https://github.com/TheTom/offlabel/blob/23d74587cb4472309702c2419451696f6f7fe242/models/nemotron-3.5-lightning-30b-a3b.md),
introduced at Offlabel commit
[`23d74587cb4472309702c2419451696f6f7fe242`](https://github.com/TheTom/offlabel/commit/23d74587cb4472309702c2419451696f6f7fe242).

Conditions reported by Offlabel:

- NVIDIA Nemotron 3.5 Lightning 30B-A3B, 31.6B total / 3.6B active;
- ggml-org Q4_K_M GGUF;
- stock llama.cpp `0b1bad1`;
- DGX Spark GB10;
- temperature 1.0, top_p 0.95;
- single tester / single seed; long-context stress not run.

### Existing Minefield owners

**Trap 12 — empty content at the token ceiling.** Offlabel reports the same
reasoning-before-answer failure shape on this newer model: with thinking on and
`max_tokens: 80`, the request reaches `finish_reason: length` with empty final
content because the reasoning consumes the budget first. The guide also reports
that NVIDIA's `force_nonempty_content` template kwarg does not rescue a budget
that is genuinely too small. A dense seven-part request is reported to have
consumed 61,984 reasoning tokens across two retries and still returned empty.
The durable lesson is already Trap 12's: budget conversion is per model and per
task, and a rescue flag cannot manufacture answer budget that is not there.

**Trap 02 / template-owned think boundary family.** With thinking disabled,
Offlabel reports stray `</think>` tokens in visible output. This is useful
external corroboration of the symptom class, but the guide does not isolate the
same parser mechanism as Trap 02's primary Laguna result. Keep it as a
cross-check, not a mechanism rewrite.

### Not promoted

The guide also reports fabricated tool-call-shaped output when thinking is off.
That may be a model-output/harness behavior rather than a parser failure. The
public guide does not establish an unambiguous serving-path mechanism, so no
tool trap is extended from that observation here.

## 2. Qwen3.6-27B Q4_K_M GGUF

Primary public guide:
[`models/qwen3.6-27b.md`](https://github.com/TheTom/offlabel/blob/746e0e7d4331d42a8368c0b0d4265432916f33ce/models/qwen3.6-27b.md),
updated at Offlabel commit
[`746e0e7d4331d42a8368c0b0d4265432916f33ce`](https://github.com/TheTom/offlabel/commit/746e0e7d4331d42a8368c0b0d4265432916f33ce).

The August pass adds a Q4_K_M / llama.cpp thinking ablation. The serving-relevant
addition is again Trap 12's failure class: reasoning runs before the visible
answer, so low `max_tokens` can end with `finish_reason: length` and empty
content. Offlabel reports the effect in the roughly 80–400 token range and
reports `enable_thinking:false` as a clean direct-answer path in that tested
configuration.

This does not create a new Qwen budget trap. Minefield already records the
family's size/task-dependent budget floors in Traps 12 and 22.

## 3. Quantization finding already owned

The Qwen guide's older but still prominent NVFP4 result is already captured in
[Trap 44](../traps/quantization/44-fp4-dequant-scale-swizzle-layout.md): a wrong
FP4 scale layout can produce a deceptively plausible cosine around 0.92 while
the model is functionally broken, whereas the corrected layout reaches about
0.9967 and coherent generation. No duplicate entry is needed.

## 4. Offlabel open issues checked

At this audit, Offlabel's open issues relevant to our shared work are:

- **#15** — one thinking-off/on Laguna agent-loop pair. Both runs failed; the
  observation is explicitly n=1 per arm and confounded. It does not overturn a
  Minefield trap or justify a new one.
- **#16** — Laguna multi-turn thinking collapse under stripped reasoning versus
  preserved reasoning. This is Blackwellboy's published `context-mass` evidence
  and is already owned by Minefield's history-reasoning entries, especially
  Trap 04. No duplicate action is needed.

Muse Glimmer is also already reconciled by the 2026-08-11 Minefield mining note
and PR #31, so this audit does not ingest it again.

## Result

- `NEW_TRAP_COUNT=0`
- Nemotron 3.5 Lightning: external corroboration for Trap 12; symptom-only
  cross-check for Trap 02.
- Qwen3.6-27B Aug 12: external corroboration for Trap 12/22.
- Qwen NVFP4 scale-layout finding: already Trap 44.
- Offlabel issues #15/#16: no new Minefield action.

**Evidence status:** contributor/external measurements, conditions as reported.
No claim in this note is a first-party reproduction unless it points to an
existing Minefield entry that independently has that status.
