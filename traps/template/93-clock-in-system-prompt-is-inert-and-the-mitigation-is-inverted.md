# Trap 93: a clock in the system prompt costs nothing on a system-relocating template, and the received fix for it is the change that actually destroys the cache

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, llama.cpp `b9878-2da668617` serving a
Mistral-family Q8_0 GGUF of unstated provenance, `--jinja`, `-np 4`. Each arm
was run against a **freshly restarted server**: see
[trap 92](../runtime/92-prompt-cache-is-a-second-divergence-source.md) for why
anything less inverts this result.

**Evidence pointer.** Four five-turn conversations, one per arm, reading
`prompt_tokens_details.cached_tokens` each turn. One script on the reader's
lane.

**Symptom.** Prefix reuse on a multi-turn lane is near zero. You apply the
standard remedy, move the volatile text out of the system prompt, and nothing
improves. Or you apply it and reuse gets dramatically worse.

## The claim being tested

Widely repeated, and reasonable: a prompt cache matches from the start of the
prompt until the first differing token, so putting a clock at the top of a
system prompt changes byte one every turn and no turn can ever reuse a prefix.
The standard remedy is to move volatile text out of the head of the system
prompt.

Both halves are wrong on this template, in opposite directions.

## Measured, four arms, fresh server per arm

`cached_tokens` per turn, five-turn conversations:

| arm | turn 1 | 2 | 3 | 4 | 5 | prompt tokens @5 | reuse @5 | prefill ms @5 |
|---|---|---|---|---|---|---|---|---|
| A1 static system prompt | 0 | 0 | 48 | 92 | 136 | 535 | 25% | 124 |
| A2 **clock at head of system prompt** | 0 | 0 | 0 | 91 | 135 | 561 | 24% | 130 |
| A3 **clock at head of first user turn** | 0 | 0 | 0 | 0 | 4 | 656 | 0.6% | 216 |
| A4 static at head of first user turn | 0 | 0 | 385 | 429 | 474 | 615 | 77% | 82 |

**A1 against A2 refutes the claim as worded.** Adding a per-turn clock to the
head of the system prompt moved reuse from 136 tokens to 135. It costs nothing,
because on this template the system block is not at the head of the prompt: the
template hoists it and re-attaches it to whichever user turn is currently last
(that is [trap 82](82-system-prompt-relocates-to-last-user-turn.md)). A clock
placed there is not in a prefix position, so it cannot bust a prefix.

**A3 against A4 confirms the mechanism, at a different position.** Same message
shape, same static padding, the only difference a per-turn clock at the head of
the first user message: reuse falls from 474 tokens to 4, and prefill rises from
82 ms to 216 ms. The mechanism the claim describes is real and severe. It is
simply not located where the claim says it is.

## Why this is worse than a plain refutation

The received advice and the received alternative are both wrong here, and the
alternative is actively harmful:

- "Keep the clock out of the head of your system prompt" is a **no-op** on this
  template: A1 and A2 differ by one cached token. An operator applying it sees
  no improvement and concludes the cache is broken.
- "Put volatile context in the first user message instead" is the single change
  that takes reuse from 77% to 0.6%, which is A4 down to A3. **The mitigation is
  inverted:** following it moves the clock out of the one position where it was
  harmless and into the one position where it is fatal.

The rule that survives is positional, not role-based: **find where the template
actually puts the head of the prompt, and keep per-turn-volatile text out of
that**, whatever role it arrives in. On a template that emits the system block
first, that is the system prompt. On this one it is the first user turn.

## A second, larger cost falls out of the same table

A1 and A4 carry the **same static text** and differ only in which role delivers
it. Reuse at turn 5: 136 tokens as a system prompt, 474 tokens inside the first
user turn, which is 25% against 77%, and 124 ms against 82 ms of prefill. On
this template, merely *using the system role* costs about 340 tokens of reuse
per turn regardless of the content, because the relocation moves the block
forward every turn. That is a larger effect than the clock, and it is invisible
to any single-turn probe.

## Check it

Render a three-turn history and see where the system text lands:

```bash
curl -s localhost:PORT/apply-template -H 'Content-Type: application/json' -d '{
  "messages":[{"role":"system","content":"SYSMARK"},
              {"role":"user","content":"U1"},
              {"role":"assistant","content":"A1"},
              {"role":"user","content":"U2"}]}'
```

If `SYSMARK` comes back next to `U2` instead of at the head, then the system
prompt is not your prefix, and clock-in-system advice does not apply to this
lane. Then confirm with two arms, volatile text at the head of the first user
turn against the same text held static, reading `cached_tokens` per turn, with a
**server restart between the arms**.

## Scope

llama.cpp `b9878-2da668617` serving one Mistral-family Q8_0 GGUF of unstated
provenance. The relocation is a property of the embedded template, so expect
this inversion wherever that template shape travels, and expect the original
advice to be correct on templates that emit the system block at the head. The
measured figures are this build and this file. We make no claim about Mistral
checkpoints generally, about any named model, or about any product.

**Related.** [Trap 82](82-system-prompt-relocates-to-last-user-turn.md)
establishes the relocation this entry measures the cost of.
[Trap 25](25-empty-think-blocks-poison-prefix-cache.md) is the other way a
template can silently cost you a prefix.
[Trap 92](../runtime/92-prompt-cache-is-a-second-divergence-source.md) is why
every arm above was run against a fresh process.

**Found.** 2026-07-28, second coverage pass on this file.
