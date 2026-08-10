# llama.cpp and GGUF

**Measured here:** yes (51 entries across our own lanes; the stack most of this registry was measured on)


**34 entries name llama.cpp or GGUF** in their evidence surfaces (see
[how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)).
This stack has the registry's densest template coverage, because it is the one
whose render route makes template forensics cheap.

## The three checks to run first

**1. Render through `/apply-template`.** It is the server's own output, not a
local Jinja re-implementation, which makes every template question here
deterministic. Run the three-turn marker probe from
[trap 04](../traps/template/04-history-reasoning-stripping.md) through it, and
diff a history sent under `reasoning` against one sent under
`reasoning_content`. On this stack the write field that survives is
`reasoning_content`; `reasoning` is silently dropped and renders
**byte-identical** to the stripped arm
([trap 20](../traps/reasoning/20-reasoning-write-field-name-diverges.md)).

**2. Assert one structured tool call, and check the serve line before the
client.** `--jinja` is the flag whose absence turns structured calls into
prose ([trap 19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md)).

**3. Read `/props`, and read it knowing what it is telling you.** Two entries
apply at once: it gives you the live server's `default_generation_settings`,
which is how you catch a checkpoint that ships no `generation_config.json`
([trap 21](../traps/versioning/21-no-generation-config-server-defaults-win.md)),
and on one measured build its context number is the **per-slot** context
rather than what you launched with
([trap 87](../traps/runtime/87-llamacpp-props-reports-per-slot-context.md)).

**4. For reasoning-strength / card-prose controls, render before you trust.**
On Muse Glimmer 30B (2026-08-11), card-style system text `Reasoning strength: low`
did not bind the template kwarg and produced a dual LOW+HIGH render while
`chat_template_kwargs.reasoning_strength=low` produced a clean LOW. Full
writeup: [mining note](../mining/2026-08-11-muse-glimmer-30b-reasoning-control-and-stack.md).
Use `/apply-template` (or equivalent) and hash the render next to every arm.

## The five that bite hardest here

| Entry | What it does to you |
|---|---|
| [19, one missing server flag turns tool calls into prose](../traps/tools/19-missing-jinja-breaks-tool-parsing.md) (**Core**) | The model "cannot tool-call", and the conclusion is attached to the model rather than to the serve line |
| [20, the reasoning write field is runtime-specific](../traps/reasoning/20-reasoning-write-field-name-diverges.md) | Trap 04's fix "does not work" because the field name was ported from a vLLM writeup. The wrong field fails by producing absence |
| [84, a completed tool round trip followed by a user turn is unrenderable](../traps/template/84-tool-roundtrip-then-user-turn-is-unrenderable.md) | An agent loop returns HTTP 400 and the error blames the template rather than your message list |
| [83, the template carries a baked default system prompt](../traps/template/83-template-carries-a-baked-default-system-prompt.md) | Your no-system-prompt control arm is not a control, because the template injects one whenever you omit it |
| [87, `/props` reports the per-slot context](../traps/runtime/87-llamacpp-props-reports-per-slot-context.md) | It reports a context length you did not launch with, exposes no trained context, and calls itself disabled while serving |

## Also worth knowing on this stack

- [82](../traps/template/82-system-prompt-relocates-to-last-user-turn.md): a
  template that moves the system prompt onto the **last** user turn, so no two
  turns share a prefix and every turn misses the cache.
- [86](../traps/template/86-final-assistant-turn-bypasses-the-template-branch.md):
  a prefilled final assistant turn behaving differently from the same text
  mid-conversation.
- [85](../traps/reasoning/85-enable-thinking-typechecked-though-never-read.md):
  `enable_thinking` type-checked by the server on a model whose template never
  reads it and which has no thinking at all.
- [24](../traps/template/24-official-template-breaks-cpp-jinja.md): official
  templates using Python-only Jinja constructs, so tools break here and work
  elsewhere.
- [45](../traps/quantization/45-fa-all-quants-cpu-fallback.md) and
  [46](../traps/versioning/46-stale-build-missing-arch-kernel.md): KV-quant
  pairs with no compiled flash-attention kernel, and a binary that predates
  its own arch-native kernel. Both are "your build decided this, not your
  config".
- [18](../traps/runtime/18-flash-attention-off-halves-deep-decode.md):
  attention implementation off, with a penalty that grows with depth, so a
  shallow bench looks fine.
- [88](../traps/runtime/88-cache-prompt-false-does-isolate-here.md): whether
  `cache_prompt: false` isolates a request is a **per-build** fact. It does on
  the one build measured here, which does not reproduce two prior stacks.

## If you care whether temperature 0 means what you think it means

- [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md):
  multi-slot batching diverges at temperature 0, but **only above a prompt
  length floor**, so the minimal reproduction most people write returns a false
  negative. Send `cache_prompt: false` and compare hashes, not samples.
- [92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md): the
  prompt cache is a second, independent divergence source, visible at
  concurrency 1, and its state survives across separate client invocations
  against one process. Restart the server between arms of a reuse comparison.
- [94](../traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md):
  the same binary and weights are batch-invariant on `sm_86` at 444 tokens and
  not on `sm_120`. Reproducibility is a per-architecture claim.
- [95](../traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md):
  a **negative**. Two lanes on two GPUs of one host, both with headroom,
  perturbed neither correctness nor decode throughput.

## What this server will not tell you about itself

- [97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md):
  partial offload costs 22 to 31 times decode and **no log line and no `/props`
  field names the split**. VRAM occupancy is not a proxy. Record a full-offload
  decode figure per file per lane, or you have no signal.
- [96](../traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md):
  under WSL2, `--list-devices` prints **host** available memory as device free
  memory, exceeding the total it prints beside it. Assert
  `free_mib <= total_mib` before believing either number.
- [93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md):
  on the relocating template above, keeping a clock out of the system prompt is
  a no-op and moving it into the first user turn is the change that destroys
  reuse. The rule is positional, not role-based.

Entries 82 through 88 and 91 through 97 came from one Mistral-family Q8_0 GGUF
of **unstated provenance** on llama.cpp `b9878`, except 96, which loaded no
model at all. The checkpoint is deliberately not characterised and nothing from
it generalises to any named model.

## Where the GGUF pipeline itself bites

- [55](../traps/evaluation/55-supported-context-is-not-trained-context.md): a
  reduced export can carry a `context_length` that is not the upstream one,
  and the KV footprint at the advertised length is frequently the real limit.
- [56](../traps/template/56-checkpoint-ships-no-chat-template.md): template
  forensics reporting "no chat template" on a model that chats fine, because
  the template is Python inside the checkpoint.
