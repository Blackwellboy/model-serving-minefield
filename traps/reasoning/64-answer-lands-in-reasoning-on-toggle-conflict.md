# Trap 64: when the template and the parser disagree, the answer is delivered as reasoning and content is null

**Found by Blackwellboy.**

**Status: reproduced here with a fully crossed six-cell control matrix, two runs
per cell, both failing rows reproducing on both runs.**

**Symptom.** A request returns HTTP 200 with `finish_reason: "stop"` and
`content: null`. Your client renders an empty message. Retrying with the same
payload reproduces it exactly. Nothing anywhere in the response indicates a
problem, and the same prompt with one word changed works perfectly.

**Mechanism.** Two components decide the same thing from two different inputs.

- The **reasoning parser** decides which response field the generated text
  belongs in, from the **request keyword** (`enable_thinking`).
- The **chat template** decides whether a think block is actually opened, from
  the **message text** (it scans for `/think` and `/no_think`; see the
  [in-text toggle draft](../template/66-in-text-thinking-toggle-mutates-user-text.md)).

When those disagree in the direction "keyword says think, text says do not", the
model produces a plain answer with no think block, and the parser, told to expect
reasoning, routes the entire answer into `reasoning` and leaves `content` null.

The trigger is a substring in the user's own text. The user is not doing anything
unusual and cannot be told to stop.

**Full control matrix.** Question "Name the largest planet", two runs each,
temperature 0:

| Request keyword | Message text | `content` | `reasoning` |
|---|---|---|---|
| `enable_thinking: true` | plain | `Jupiter` | 133 chars of trace |
| `enable_thinking: true` | contains `/no_think` | **null** | `Jupiter` |
| `enable_thinking: false` | plain | `Jupiter` | absent |
| `enable_thinking: false` | contains `/think` | `Jupiter` | 342 to 773 chars of trace |
| keyword absent | plain | `Jupiter` | 133 chars of trace |
| keyword absent | contains `/no_think` | **null** | `Jupiter` |

Two things worth reading off this table. The failure is **asymmetric**: the
opposite conflict (`false` keyword, `/think` text) is benign, because content
still lands in `content` and you merely get an unrequested trace. And the
**keyword-absent** row fails identically to the explicit-true row, so a client
that never sends the keyword at all is equally exposed.

Reproduced with an image attached in the same request shape.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node, reasoning
parser `nemotron_v3`, tool parser `qwen3_coder`, prefix caching on.

**The check.** Two requests. Send your normal prompt, then send it again with
`/no_think` appended somewhere harmless, both with your usual `enable_thinking`
setting. Assert `content` is a non-empty string on both. More generally: **assert
non-empty content on every response**, and treat a null with `finish_reason:
"stop"` as a hard failure rather than an empty answer, because those are two
different things and only one of them is the model's opinion.

**The fix.** There is no server-side switch. Client-side, in order of
effectiveness:

1. Strip or escape `/think` and `/no_think` from user text before sending.
2. Assert `content` is non-empty. If it is null and `reasoning` is populated and
   `finish_reason` is `stop`, treat the reasoning field as the answer, or fail
   the request. Do not render an empty message.
3. On the sibling checkpoint in this family, a shipped parser kwarg
   (`force_nonempty_content`) does exactly this rescue server-side; see the
   [parser-only rescue kwarg draft](65-parser-only-rescue-kwarg.md). It was
   not tested on this checkpoint's parser and may not be read there.

**If you miss it.** An agent loop receives an empty assistant turn from a request
that succeeded, and either retries forever, or writes the empty string into its
own history and continues from a conversation that now demonstrates the assistant
answering nothing. An evaluation harness scores it zero and attributes the zero
to the model.

**Negatives recorded.**

- Both failing rows reproduced on both runs at temperature 0, so this is not
  sampling.
- The reverse conflict does not lose the answer; only one direction is fatal.
- HTTP status, `finish_reason`, and the usage block are all indistinguishable
  from a successful request. There is no signal to alert on except the null
  itself.

**Related.**
[trap 23](23-streaming-answer-lands-in-reasoning-channel.md) is the same
destination reached by a different route (streaming delta placement);
[trap 29](29-server-reasoning-off-is-not-an-off-switch.md) is the neighbouring
case where the off switch is not one;
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) is the other way to
get `content` empty, distinguishable by `finish_reason: "length"` and by the
reasoning being a genuine trace rather than the answer itself. Telling those two
apart matters: the ceiling case is fixed with a bigger budget and this one is
not.

**Found.** 2026-07-27.

**Attribution.** Blackwellboy.
