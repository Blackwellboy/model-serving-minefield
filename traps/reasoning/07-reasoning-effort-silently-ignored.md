# Trap 07: `reasoning_effort` accepted and silently ignored

**Found by @quantumleap68.**

**Status: reported by others and reproduced here on a second family and stack** (@quantumleap68 wire-level on Laguna/vLLM; reproduced on two Qwen models on llama.cpp, and on a third stack, mlx_lm, see below).

**Symptom.** Effort levels change nothing. Identical reasoning depth at
`low`, `medium`, and `high`, and you conclude the model ignores depth
requests, or worse, publish a "reasoning_effort has no effect on this model"
finding as if the knob had been exercised.

**Mechanism.** The request schema accepts a `reasoning_effort` parameter,
the server returns 200, and the chat template has **no handling for it at
all**. The parameter parses, validates, and does nothing. On templates like
this, prompting is the only depth lever that exists.

**Stacks and builds bitten.** Laguna S 2.1 on vLLM 0.25.1, measured at the
wire by @quantumleap68 (his CLI client, logging proxy): `reasoning_effort` is a
no-op because the template never reads it. Same class as Trap 04's corollary
in reverse: there, the template read a kwarg the model card did not document;
here, the API accepts a parameter the template does not read. Both directions
of the schema/template mismatch produce silent wrong numbers.

Reproduced on two more models on llama.cpp (2026-07-27, standardized probe
sweep): `reasoning_effort` low versus high moved measured reasoning length
by noise only on Qwen3.6-27B Q4_K_M (1,996 vs 1,989 chars, llama.cpp b9193)
and Qwen3.5-9B Q4_K_M (2,376 vs 2,528 chars, b9066); both templates read
`enable_thinking` and neither reads `reasoning_effort` (template text
inspected live via `/props`). Related surface: llama.cpp accepted a
deliberately bogus `chat_template_kwargs` key with HTTP 200 on both lanes,
so the entire kwargs dict is send-and-pray on this server: nothing
validates that any key you send is read. The grep-the-template check is the
only real one.

**Third stack: mlx_lm, with a WIDER acceptance surface (confirmed
2026-07-27).** Stock mlx_lm serving prism-ml Ternary-Bonsai-27B-mlx-2bit on
Apple silicon. Three acceptance probes, all HTTP 200, all normal replies:
a `chat_template_kwargs` containing only an invented key; an invented
TOP-LEVEL body key; and `reasoning_effort` as a top-level OpenAI-style
parameter. On this stack even the request body schema is unvalidated, one
level up from the llama.cpp finding above: a typoed `max_tokens` (say
`max_token`) would be silently dropped and the request would run with
defaults, so any config typo becomes a silent behavior change instead of a
400. The shipped template (chat_template.jinja next to the weights on MLX
model dirs) reads exactly two request-controllable kwargs, `enable_thinking`
and `preserve_thinking`, and never references `reasoning_effort`: a dead
knob in both positions while the server 200s both. The one kwarg the
template DOES read behaved as documented, so acceptance-versus-effect on
this lane splits exactly along template-reads-it lines.

**The check.** Grep the chat template for the parameter name **before**
trusting any knob you send. If the template never references it, the knob is
dead on this build regardless of what the server accepts. The general rule:
diff the set of kwargs the template reads against the set the API accepts,
in both directions.
[`checks/preflight_template.py`](../../checks/preflight_template.py) enumerates
the template's kwarg surface for you.

**The fix.** Remove the dead knob from your configs and your conclusions.
If you need depth control on such a template, it has to come from the prompt.

**Found.** 2026-07-27, reported from wire-level measurement.

**Attribution.** @quantumleap68.

## Added 2026-07-28: a family whose template reads three kwargs and whose card documents one

**NVIDIA Nemotron 3 family, three checkpoints (Nano 30B A3B NVFP4, Nano Omni 30B A3B NVFP4, Super 120B A12B NVFP4), GB10-class single nodes, vLLM 0.20.0 and 0.25.1.** The template reads `enable_thinking` (documented), `low_effort`
(undocumented, default false) and `truncate_history_thinking` (undocumented,
**default true**, and it changes multi-turn behaviour silently). This is the
read-but-undocumented side of this entry rather than the accepted-but-unread
side, and it is the more expensive of the two, because an undocumented kwarg
with a non-neutral default is an uncontrolled variable in every result you take
on that lane.

`low_effort` works and is worth knowing about: reasoning length fell from about
190 characters to 46 with content preserved and correct. Note **where** it
lands: appended to the **last user message**, not to the system message, so any
client that hashes user content for caching or deduplication sees a different
message depending on it.

There is also a fourth kwarg read by the **reasoning parser** and not by the
template at all, which is [trap 65](65-parser-only-rescue-kwarg.md). The
history gate is [trap 63](63-reasoning-round-trip-one-correct-shape.md).

*Status of this addendum: reproduced here. The kwarg enumeration runs offline
against the public chat template.*

## Added 2026-08-11: Muse Glimmer 30B on llama.cpp - low/high dead; only `"none"` special-cased

**Muse Glimmer 30B UD-Q4_K_XL, llama.cpp `62bf73d25`, Unsloth pin `9889697...`, single-GPU.** Template text has **zero** references to `reasoning_effort`. Historical clean renders with `reasoning_effort=low` matched the bare default (template default `reasoning_strength=high`). Bounded runtime did not show the intended low/high depth control. Server source on this path special-cases `reasoning_effort="none"` and does not implement the other values as strength controls.

This is the same accepted-and-unread class as the original entry, on a new model family and a documented server-side narrow exception: **do not infer that `"low"`/`"high"` work because `"none"` exists.**

*Status of this addendum: measured here, raw not published.* Full bounded campaign writeup: [mining note](../../mining/2026-08-11-muse-glimmer-30b-reasoning-control-and-stack.md).

## Added 2026-08-15: Qwen3.8 NVFP4 — `medium` is accepted but has no instruction branch

**Independently reproduced here by Blackwellboy** on
`RadixArk/Qwen3.8-27B-NVFP4@52d1adc`, template SHA
`c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041`.

This is the **accepted-but-partially-implemented** shape of the same class:
the template *does* read `reasoning_effort`, validates the set
`{xhigh, medium, low}`, and injects instructions for **xhigh** and **low**
only. There is **no** `elif` for `medium`, so medium renders without any
effort system instruction (and without the xhigh/low strings).

- `medium` render SHA: `575d9cb4b43894c0dcd0184639dbb765f8073a9263ca25385e3cfb34d6a81751`
- `high` raises: `Unexpected reasoning effort high. Supported types are xhigh (default), medium, and low.`

Do not publish “medium reasoning” results on this pin without dumping the
rendered prompt. A 200 from the server is not proof of medium semantics.

Public check:
[`checks/reproduce_qwen38_reasoning_config_traps.py`](../../checks/reproduce_qwen38_reasoning_config_traps.py).

Prior public lead / report: TheTom/offlabel. Independent first-party
reproduction: Blackwellboy.

*Status of this addendum: reproduced here (runnable public template check).*
