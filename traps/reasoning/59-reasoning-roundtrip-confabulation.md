# Trap 59: the model quotes reasoning that was deleted before it ever saw the prompt

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on a live DeepSeek-V4-Flash lane.
Field naming confirmed against the response bodies; the stripping confirmed
against the server's own assembled prompt, so this is not inferred from
behaviour.

**Evidence pointer.** Both halves are checkable without us. The discarding of
prior-turn reasoning is in the checkpoint's Python prompt builder, a public
source file; the field the server writes is decided by the vLLM reasoning
parser named in the serve line, also public source. The two-step probe in the
check section then confirms it end to end on the reader's own lane. The
confabulation itself is a consequence of those two facts, not a separate
measurement to take on trust.

**Symptom.** You build a multi-turn agent that keeps the model's reasoning in
the conversation so later turns can build on it. It appears to work. Ask the
model in turn two what it was thinking in turn one and it answers confidently,
in first person, with a blockquote: *"Here is the relevant quote from that
response..."*. The quote is fabricated. The reasoning was removed from the
prompt before the model ran, and the model is reconstructing a plausible
account of thoughts it cannot see.

This is worse than the reasoning simply being dropped, which is
[trap 04](../template/04-history-reasoning-stripping.md). Dropped context
usually announces itself: the model says it does not recall, or contradicts
itself, and you notice. Here the failure is **silent and confident**, and a
human reviewing the transcript sees a coherent self-report and concludes the
history plumbing works.

**Mechanism, in three parts that each have to be checked separately.**

*One: which field the server writes.* On this stack the assistant message
carries reasoning under the key **`reasoning`**. There is no
`reasoning_content` key at all. That is the opposite of the convention this
model family's own hosted API uses, which is `reasoning_content`. So a client
written against the vendor's API documentation reads `reasoning_content`, gets
nothing, and concludes the model never reasons. That is
[trap 01](01-reasoning-field-two-names.md) with a specific and unusually
misleading polarity: the vendor's own name is the wrong one here. The full set
of message keys returned is `annotations, audio, content, function_call,
reasoning, refusal, role, tool_calls`, so the absence is real rather than a
null.

*Two: which field the template reads back.* Neither. Resending prior reasoning
as `reasoning_content` and resending it as `reasoning` both produce an
assembled prompt with no reasoning in it. The registry's doctor independently
tried both names plus four known preservation kwargs against this lane and
found no path that reaches the prompt. So this is not
[trap 20](20-reasoning-write-field-name-diverges.md)'s "you resent it under the
wrong name" case, which has a fix. On this lane there is **no name that works**.

*Three: what the prompt actually contains.* The assembled history renders each
prior assistant turn as a closing think tag followed by the answer text, then
an end-of-sentence marker. The reasoning is gone and the tag that used to
delimit it remains. A side effect worth knowing if you count tags: a
three-turn conversation on a thinking-off lane renders with more closing think
tags than opening ones, because the closing tag is also how this family starts
an assistant turn (see
[trap 56](../template/56-checkpoint-ships-no-chat-template.md)). A checker that
flags unbalanced think tags as broken history assembly will fire here on
behaviour that is, on this stack, entirely by design.

**Measured.** Turn one with thinking on returned 298 characters of reasoning
under `reasoning`. That text was resent in turn two under both field names.
The assembled prompt for turn two contained none of it. Asked to quote its
previous reasoning, the model produced a fluent first-person paragraph
introduced as a direct quotation, describing a rationale it had no access to.

**Why it matters beyond tidiness.** Any agent design that depends on reasoning
persisting across turns is not doing what its author believes on this lane:
scratchpad-style planning, self-critique loops, and multi-step tool agents that
re-read their own earlier deliberation. Worse, the confident confabulation
means your evaluation of those designs will pass. If you score turn two on
whether the model "remembered" its plan, it will score well by inventing one.

**The check.** Two steps, and do not skip the second, because step one alone is
what produces false confidence.

1. Read one real response body and list the message keys. Do not assume either
   field name, including the one in the vendor's own API documentation.
2. Resend a prior turn's reasoning and then look at the **assembled prompt**,
   not the model's answer. Use the server's render endpoint if it has one
   (`/v1/chat/completions/render` here) and search it for a distinctive string
   you planted in the reasoning. If the string is absent, the reasoning is not
   reaching the model no matter how convincingly the model discusses it.
   Asking the model whether it remembers is not a test; on this lane it answers
   yes either way.

**The fix.** If you need prior reasoning to survive on a lane like this, carry
it yourself as ordinary assistant **content**, or as a user-turn summary you
control, rather than in a reasoning field the template discards. Then it is
visible in the render, it is stable for prefix caching, and it costs tokens you
can see and budget. And in any multi-turn evaluation, verify the history
reached the prompt before you attribute a score to memory.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3` serving a
community-abliterated DeepSeek-V4-Flash checkpoint, tokenizer mode
`deepseek_v4`, `--reasoning-parser deepseek_v4`, `--trust-remote-code`, two DGX
Spark GB10 nodes. The stripping happens in the checkpoint's Python prompt
builder, so it travels with the checkpoint; the response field name is the
server's reasoning parser, so that half travels with the vLLM version.

**Found.** 2026-07-28, first registry coverage pass on this lane. The
confabulation was found by asking the model to quote itself rather than to
summarise itself, which is a cheap probe worth reusing.

**Attribution.** Blackwellboy. Related:
[trap 01](01-reasoning-field-two-names.md),
[trap 04](../template/04-history-reasoning-stripping.md),
[trap 20](20-reasoning-write-field-name-diverges.md),
[trap 56](../template/56-checkpoint-ships-no-chat-template.md).
