# Trap 58: reasoning_effort is an undocumented thinking switch, and at its top level it edits your prompt

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on a live DeepSeek-V4-Flash lane whose
serve line sets thinking **off** by default. Every row below is from the
server's own render endpoint and from real completions, not from reading the
template.

**Evidence pointer.** The preamble text and the toggle both live in the
checkpoint's Python encoder module, a public source file: grep it for the
effort parameter and you will find both the branch that turns reasoning on and
the literal string it prepends. The render comparison in the check section runs
against the reader's own endpoint. Neither needs anything from us.

**Symptom.** You are running a reasoning-off lane and you size every client's
`max_tokens` for non-thinking replies. One client sets `reasoning_effort`,
because it is a standard OpenAI-compatible field and it is supposed to be a
budget hint. That client starts getting HTTP 200 responses with **empty
content**, a populated reasoning field, and `finish_reason: length`. Nothing in
the request mentioned thinking. Nobody changed the serve line.

**Mechanism, and it has two halves that most people will get backwards.**

*Half one: the parameter is a thinking switch.* On this stack, sending
`reasoning_effort` as a **top-level** request field turns reasoning on for that
request, regardless of the server's thinking-off default. It is not a budget
hint and it is not advisory. Measured on the live lane, user message "hi",
`max_tokens` 4:

| request | prompt tokens | reasoning field populated | content |
|---|---|---|---|
| baseline | 5 | no | "Hello! How can" |
| `reasoning_effort: "low"` | 5 | **yes** | **empty** |
| `reasoning_effort: "max"` | **84** | **yes** | **empty** |
| `chat_template_kwargs: {"reasoning_effort": "max"}` | 5 | no | "Hello! How can" |

Read the `low` row carefully, because it is the trap inside the trap. At
`low` the prompt is unchanged, so nothing looks different in your token
accounting, and reasoning is switched on anyway. A client that sets
`reasoning_effort: "low"` **to be cheap** has instead enabled thinking on a
lane sized for non-thinking output, and at a small budget the entire allowance
is consumed by reasoning and the content comes back empty. The cheap-sounding
value is the one with no visible fingerprint.

*Half two: at the top value it also injects text.* `max` prepends roughly
seventy-nine tokens of second-person instruction to the prompt, telling the
model to be exhaustive, decompose the problem, stress-test its logic against
adversarial cases and write out its entire deliberation. The client never sees
that text; it appears in no response field. On this family it lands **above**
your system message, and since this family has no system role delimiter at all
(see [trap 56](../template/56-checkpoint-ships-no-chat-template.md)), your
system prompt becomes a continuation of a paragraph you did not write, and your
opening identity sentence is no longer in first position, which is the
precondition for [trap 06](06-identity-sentence-eviction.md).

**The same name in two places does opposite things.** Top-level
`reasoning_effort` is honoured. The identical key inside
`chat_template_kwargs` is **silently ignored**: same prompt length, no
reasoning, normal content. Both return 200. So an operator who moves the
parameter into the kwargs bag to be explicit has silently disabled it, and an
operator who audits only the kwargs bag will not find the caller that is
actually turning thinking on.

**Why this is not trap 07, and why both entries are needed.**
[Trap 07](07-reasoning-effort-silently-ignored.md) is the case where the
template never reads the parameter and nothing happens. That is exactly what
this lane does for the **kwargs** spelling, so trap 07 is also true here. What
this entry adds is that the **top-level** spelling on the same lane is not
inert at all: it flips reasoning on and, at one value, rewrites the prompt. An
operator who has read trap 07 and concluded "this field is inert, safe to pass
through" will pass it through, and on this stack that is both a budget change
and a prompt injection performed by their own serving path.

**The check, and one warning about how you check.** Ask the server what it
actually built, twice, once with the field and once without, and compare
`prompt_tokens` and whether the reasoning field is populated. Do it at **more
than one value**: `low` and `max` behave differently here, and testing only
`max` will make you think the tell is always a token-count jump when at `low`
there is none.

The warning: **check on the endpoint you actually serve from.** This server
exposes two render surfaces and they do not agree. `/v1/chat/completions/render`
faithfully reproduces the injected preamble and the toggle. `/tokenize` silently
drops the top-level field and reports the baseline length, because
`reasoning_effort` is not part of its request schema. A tokenize-based preflight
therefore returns a **false clean** for exactly this trap. Render if your server
has it; if it does not, fall back to comparing `prompt_tokens` on real
completions, which cannot be faked.

**The fix.** Decide deliberately, then enforce it at the gateway. If you want
the deliberation paragraph, write it into your system prompt yourself where you
can see it, version it, and keep it stable for prefix caching, and stop sending
the field. If you do not, strip `reasoning_effort` at the gateway rather than
letting callers pass it through, and strip it at the **top level**, which is the
one that works. Treat any caller that sets it as changing the prompt and the
budget, not the sampling. And record which arms set it next to any benchmark,
because an arm that sets it and an arm that does not are not running the same
prompt, a [trap 17](../evaluation/17-per-arm-recommended-sampling-confound.md)
confound hiding in a field nobody prints.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3` serving a
community-abliterated DeepSeek-V4-Flash checkpoint, tokenizer mode
`deepseek_v4`, `--trust-remote-code`,
`--default-chat-template-kwargs {"thinking": false}`, two DGX Spark GB10 nodes.
The injected text lives in the checkpoint's own Python prompt builder, so it
travels with the checkpoint; the top-level-versus-kwargs asymmetry is the
server's parameter mapping, so that half travels with the vLLM version.

**Found.** 2026-07-28, first registry coverage pass on this lane. The
`low`-value case was found only because the probe sweep tested a second value
after the first one produced a token-count jump.

**Attribution.** Blackwellboy. Related:
[trap 07](07-reasoning-effort-silently-ignored.md) (the inert spelling, also
true on this lane),
[trap 29](29-server-reasoning-off-is-not-an-off-switch.md) (a server thinking
default is not a gate; this is a second, unadvertised way through it),
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) (where the
reasoning tokens land you),
[trap 06](06-identity-sentence-eviction.md),
[trap 56](../template/56-checkpoint-ships-no-chat-template.md).
