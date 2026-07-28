# mlx_lm on Apple silicon

**9 entries name mlx_lm or MLX** in their evidence surfaces (see
[how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)):
one numbered for this stack, and eight where an MLX-scoped section was added
to an existing entry. All of it was measured on a stock mlx_lm server running
a 2-bit MLX build on Apple silicon.

Two properties shape everything below. Launch flags on this stack are
**defaults rather than guarantees**, and the template ships as a file on local
disk rather than behind a render route, so the checks that need an assembled
prompt have to be run against the file.

## The three checks to run first

**1. Send one request with `max_tokens` greater than the server flag and read
`usage.completion_tokens`.** The server's `--max-tokens` is a per-request
default, not a cap, so a client quietly runs past the limit you sized the lane
with ([trap 32](../traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md)).
Worth doing on any stack whose launch flags you are treating as guarantees.
The same shape one knob over: a server-side thinking-off setting is a default
a client kwarg can override
([trap 29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)).

**2. Read `message.reasoning`, and use `.get` on `content` too.** On this
stack reasoning arrives under `reasoning` only; `reasoning_content` never
appeared in any probe. And an empty channel is an **absent key**, not an empty
string: a thinking response that hit the cap had no `content` key at all, so
`msg["content"]` raises on every thinking cap-hit and `msg.get("content", "")`
silently converts a budget artifact into "the model returned nothing"
([trap 01](../traps/reasoning/01-reasoning-field-two-names.md)).

**3. Run the template checks against the file.** The doctor's
history-assembly checks skip here, because the template ships as
`chat_template.jinja` next to the weights and there is no render route to
reach. Use [`checks/preflight_template.py`](../checks/preflight_template.py),
which accepts `--template-file`. Doing this by hand on the measured lane found
a real write-field divergence that the skip had left invisible
([trap 20](../traps/reasoning/20-reasoning-write-field-name-diverges.md)).

## The five that bite hardest here

| Entry | What it does to you |
|---|---|
| [32, the server `--max-tokens` flag is a per-request default](../traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md) | You sized the lane with a limit that does not bind. Put the clamp in a gateway you control |
| [01, the reasoning field has two names](../traps/reasoning/01-reasoning-field-two-names.md) (**Core**) | Only `reasoning` exists here, absent keys rather than empty strings, and every streaming delta carries `role="assistant"` so a naive client fragments the stream |
| [20, the reasoning write field is runtime-specific](../traps/reasoning/20-reasoning-write-field-name-diverges.md) | The server emits `reasoning` while the shipped template's history path reads the other name, so trap 04's fix does not port |
| [29, server thinking-off is not an off switch](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) | A launch-flag thinking default a client kwarg overrides, which is a budget hazard on a lane sized for non-thinking output |
| [07, `reasoning_effort` accepted and silently ignored](../traps/reasoning/07-reasoning-effort-silently-ignored.md) | A wider acceptance surface than the other stacks: the knob is dead and the server does not tell you |

## Also worth knowing on this stack

- [12](../traps/evaluation/12-empty-content-at-token-ceiling.md): the
  empty-content-at-cap shape, on a response whose `content` key was entirely
  absent.
- [03](../traps/reasoning/03-enable-thinking-default-drift.md): mlx_lm injects
  template kwargs server-side via a launch flag, so the "who supplies the
  kwarg" arm has its own spelling here.
- [13](../traps/memory/13-utilization-fraction-on-unified-memory.md): Apple
  silicon is a unified-memory box, so pin the KV cache in bytes rather than by
  fraction.

## What the doctor can and cannot do here

The doctor ports cleanly for 6 of its 9 check families on this stack. Two
honest gaps, both coverage gaps rather than wrong answers: it cannot identify
the stack (no `/props`, no `/version`), and the history-assembly checks skip
for want of a render path. The field report is in
[doctor/README.md](../doctor/README.md#portability-notes-mlx_lm-first-field-run-2026-07-27),
and it is dated on purpose: several verdicts in it have since been
re-classified, so do not quote a verdict from it without re-running at the
current tip.

A [clean preflight](../models/README.md#clean-preflights) is also recorded for
this lane. It says "checked, nothing found" for what it checked, and a deeper
same-day pass then found the coverage above.
