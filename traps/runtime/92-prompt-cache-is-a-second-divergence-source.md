# Trap 92: the prompt cache is a second, independent source of temperature-0 divergence, and it survives long enough to invert an A/B run against it

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, llama.cpp `b9878-2da668617` serving a
Mistral-family Q8_0 GGUF of unstated provenance, `--jinja`, `-np 4 -fa on`.

**Evidence pointer.** Two runs of the same four-arm probe against the same lane,
one with a server restart between arms and one without. Both are one script on
the reader's own lane.

**Symptom.** You disable nothing, run a prefix-reuse comparison twice to be
careful, and the two runs disagree about which arm is better. Or a
concurrency-1 lane, which cannot be batching anything, returns two different
answers to the same temperature-0 request.

## Part 1: divergence at concurrency 1, which should be impossible

With `cache_prompt: false`, concurrency-1 cells were byte-identical in 512/512
responses. With the cache left at its default, which is on, the same
concurrency-1 cells diverge:

| cache_prompt | concurrency | cells diverging | responses off majority |
|---|---|---|---|
| `false` | 1 | 0/64 | 0/512 |
| default (on) | 1 | 2/6 | 2/48 |

In every concurrency-1 divergence the odd response was the one with a *partial*
cache hit, meaning `cached_tokens` below the full prompt, against a majority
that got the full prefix back. So a prompt replayed from a partial cache does
not produce the same logits as the same prompt replayed from a complete one.

This is a **separate** effect from the batching one in
[trap 91](91-concurrency-nondeterminism-has-a-prompt-length-floor.md). It needs
no concurrency, and it is switched off cleanly by `cache_prompt: false`. Anyone
investigating concurrency non-determinism without disabling the cache is
measuring both at once, and will attribute one to the other. The two must be
separated before either can be characterised, and disabling the cache is the
separation.

## Part 2: the cache outlives the thing you are A/B-ing, and inverted our result

This is the part that nearly published a wrong number, and it is recorded
because the failure was ours.

We ran a four-arm probe measuring how much prefix a multi-turn conversation can
reuse. One arm, a per-turn clock at the head of the first user message,
collapsed reuse to almost nothing. We then re-ran the arms in the **reverse
order against the same long-lived server process** as a check. The same arm came
back showing near-total reuse:

| same arm, same server config | `cached_tokens` by turn |
|---|---|
| first run (arm ran 3rd) | 0, 0, 0, 0, 4 |
| reversed-order run, same process | 464, 508, 557, 606, 655 |

Nothing about the arm changed. The requests were byte-identical. The second run
inherited hits from the first, because the prompt cache persists across arms
**and across separate client invocations against one server process**, and it
retained prompts issued roughly a thousand requests earlier. Both runs were
internally consistent; one of them was measuring the other one's history.

**The conclusion inverted.** Judged on the second run, the arm looks like the
*best* configuration. Judged in isolation, it is the worst. Either number is
defensible-looking on its own, and the direction of the finding flips on which
one you happen to run.

**What actually isolates it.** Not a flush request, and not reversing the order.
Restarting the server process between arms. On a fresh process, turn 1 of every
arm reports `cached_tokens: 0`, which is the only state you can trust as a
baseline:

| arm, fresh process each | `cached_tokens` by turn |
|---|---|
| static text at head of first user turn | 0, 0, 385, 429, 474 |
| per-turn clock at head of first user turn | 0, 0, 0, 0, 4 |

`cache_prompt: false` is **not** a substitute here: it disables reuse entirely,
so it measures no reuse rather than clean reuse, and says nothing about how much
reuse a configuration *would* get. It is the right tool for
[trap 91](91-concurrency-nondeterminism-has-a-prompt-length-floor.md) and the
wrong tool for this.

## Check it

1. Run any prefix-reuse A/B twice against one long-lived server, in opposite arm
   orders. If the arms disagree between the two runs, the cache is carrying
   state.
2. Confirm the isolation is real by asserting `cached_tokens == 0` on the first
   request after each restart. If it is not zero, the arm is contaminated and
   the number should not be reported.

## Scope

llama.cpp `b9878-2da668617`, one Mistral-family Q8_0 GGUF of unstated
provenance. The retention behaviour is a server property, not a model property.
The specific figures are from this build and this file; the methodological
point, that a reuse A/B needs process-level isolation and that skipping it can
reverse the sign of the answer, is not build-specific and is the reason this is
written up. We make no claim about Mistral checkpoints generally, about any
named model, or about any product.

**Related.** [Trap 54](../evaluation/54-run-order-and-warm-cache-artifacts.md)
is the general run-order and warm-cache class this belongs to.
[Trap 60](60-cold-prefill-and-cache-hit-disagree.md) is the same divergence
observed on a different stack, as a verdict flip rather than a byte difference.
[Trap 93](../template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md)
is the study whose result this inverted, re-measured with a restart per arm.

**Found.** 2026-07-28, second coverage pass on this file, as a self-caught
error.
