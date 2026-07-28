# Trap 69: three low-severity template defects that break assertions and waste tokens

**Found by Blackwellboy.**
each is too small to carry a number alone and they share a cause: guards that
were written for a case the template can never reach.

**Status: reproduced here.** All three are visible in rendered output, with the template line
that causes each one identified.**

These are not going to change anyone's numbers. They are here because each one
breaks a reasonable assertion, and because an operator who finds one of them
while auditing a prompt should be able to confirm it is known rather than spend
an hour on it.

---

## 1. An empty system turn on every request that sends no system message

Rendered with a single user message, no system message, no tools:

```
<|im_start|>system
<|im_end|>
<|im_start|>user
Hi<|im_end|>
<|im_start|>assistant
<think>
```

**Cause.** The template assigns `system_message` in **both** branches of its
`if messages[0].role == "system"` check, to the content or to the empty string.
It then guards emission with `if system_message is defined`, which is always
true. The `else` branch written to handle the no-system case, which emits a
system block only when tools are present, is **unreachable**.

**Consequence.** A few wasted tokens on every request, rendered prompts that are
confusing to audit, and a broken assertion for any code that checks "no system
block appears unless I sent one". If you are diffing prompts to find something
else, this is the artefact you will notice first and it is not your bug.

**Confirmed on two checkpoints** of the family.

---

## 2. A tool message in first position renders unbalanced control markup

Messages: one `tool`, then one `user`:

```
<|im_start|>system
<|im_end|>
<tool_response>
result-payload
</tool_response>
<|im_end|>
<|im_start|>user
now what<|im_end|>
```

The `<tool_response>` block has a **closing** `<|im_end|>` and **no opening**
`<|im_start|>user`.

**Cause.** The template opens the wrapping user turn only when the previous
message exists and is not itself a tool message. In first position the previous
message is undefined, the guard fails closed, and the opener is skipped while the
closer is emitted unconditionally.

**Consequence.** Malformed control markup, not an error. Reachable in practice
whenever an agent framework trims a context window so that a tool result becomes
the first surviving message, which is a normal thing for a long-running agent to
do. What the model makes of an unbalanced turn boundary was not measured.

**Confirmed on one checkpoint**; the sibling templates were not probed for it.

---

## 3. Whitespace artefacts: a leading newline, and indentation before assistant turns

Every rendered prompt begins with a **stray newline** before the first
`<|im_start|>`, from a macro definition block whose closing `{% endmacro %}` is
not whitespace-trimmed. The very first token of every prompt is a newline.

Multi-turn renders carry a run of literal spaces and newlines between turns:

```
<|im_end|>\n\n        \n            <|im_start|>assistant
```

from block-level conditionals in the assistant branch that are not fully trimmed.
A few tokens per assistant turn, growing with conversation length.

**Consequence.** Pure waste, plus prompt-hash instability for anyone keying a
cache on a normalised prompt string.

---

## The check for all three

Render a prompt and read it. Specifically: render with no system message and grep
for a system block; render with a `tool` message first and count
`<|im_start|>` against `<|im_end|>`; render anything and look at the first
character.

The registry doctor's tag-balance check catches the second one on any lane with a
render path, which since this session includes vLLM lanes.

## The fix

None client-side worth the effort, except to stop asserting things that are not
true. Report upstream: all three are one-line template fixes.

**Related.** [trap 24](24-official-template-breaks-cpp-jinja.md) and
[trap 30](30-default-system-message-silently-replaced.md), the neighbouring
"the shipped template is not what you think" entries.

**Found.** 2026-07-27 and 2026-07-28.

**Attribution.** Blackwellboy.
