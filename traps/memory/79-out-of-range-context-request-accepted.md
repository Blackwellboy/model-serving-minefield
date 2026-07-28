# Trap 79: you asked for five times the model's context and got HTTP 200

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on Ollama 0.32.5 with `qwen3:8b`
(declared context 40,960) on GB10 aarch64. One request reproduces it against
any install of that stack.

**Symptom.** You set the context size on a request, get **HTTP 200**, and the
response has **empty content** and `done_reason: "length"`. Nothing says the
context value was out of range. Nothing says it was clamped, either, so you
cannot tell from the response whether you got what you asked for, a smaller
number, or a default.

Measured: `num_ctx: 200000` against a model declaring 40,960 returned 200,
`done_reason: length`, empty content. No error, no warning, no clamp message.

**Mechanism.** The context request is not validated against the model's own
declared window. It is accepted, something else happens internally, and the
observable result is an ordinary-looking budget exhaustion. That collapses two
very different conditions into one response shape:

- a genuine token-budget exhaustion, which a bigger budget fixes, and
- a context request the server could never honour, which a bigger budget makes
  worse.

Both present as `done_reason: length` with empty content, so the natural next
move (raise the number) is the wrong one in the second case, and it is the case
you are in.

**Why it is filed here rather than with the ceiling entry.** The empty-content
outcome is the same family as
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md), and if you arrive
holding an empty `content` you should read that entry first. What is new here is
that the **context** parameter, not the output budget, is the thing out of
range, and that nothing in the request or the response distinguishes them. Trap
12 tells you to raise the ceiling; this entry is the case where that advice does
not apply and you need to look at `num_ctx` instead.

**Stacks and builds bitten.** Ollama 0.32.5, `/api/chat`, `qwen3:8b`, GB10
aarch64 CUDA 13. This is the same unvalidated request surface as
[trap 77](../reasoning/77-only-one-request-field-is-validated.md), reached
through a parameter that does have an effect, which makes it harder to spot:
there, a dropped field changed nothing; here, an unhonoured field changes
everything.

**The check.** Read the model's declared context before you set one, then assert
you are under it:

```bash
# what does the model actually declare?
curl -s localhost:11434/api/show -d '{"model":"qwen3:8b"}' | grep -i context_length
```

Then run the same request twice, once at a sane `num_ctx` and once at the value
you meant to use. If the sane one returns content and the large one returns
empty with `done_reason: length`, you are out of range rather than out of
budget. Do not raise `num_predict` to fix it.

**The fix.** Clamp `num_ctx` client-side against the model's declared
`context_length`, and refuse rather than truncate when a caller exceeds it, so
the failure is loud on your side since it is not loud on the server's. Log the
value you sent alongside every result; a run whose context parameter is not
recorded cannot be diagnosed later.

**Found.** 2026-07-28, during first-party Ollama coverage.

**Attribution.** Blackwellboy. Related:
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md),
[trap 13](13-utilization-fraction-on-unified-memory.md),
[trap 77](../reasoning/77-only-one-request-field-is-validated.md).

## Added 2026-07-28: sizing max_tokens to the model rather than to the serve

**Found by [@drowzeys](https://github.com/drowzeys) (Keys)**, shared from his public notes at [notes-for-DSV4F-DSpark-Abliteration](https://github.com/drowzeys/notes-for-DSV4F-DSpark-Abliteration). **Status: reported by others.** Not reproduced here.

This entry is about a **context** request the server accepts and cannot honour.
Keys reports the mirror-image sizing error on the **output** side: `max_tokens`
chosen from what the model advertises rather than from what the lane was
actually launched with. The two share a cause, which is that a number taken
from the model card is not a statement about the running server, and they share
a symptom, which is a request that is accepted and then cannot complete.

The practical rule is the one this entry already gives, applied to the other
parameter: read what the **serve line** established, not what the checkpoint
advertises, and clamp client-side against that.
