# Trap 55: the context length it *supports* is not the context length it was *trained* at

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Symptom.** A model advertised at a long context serves happily at that length, no error, no
warning, no truncation, and then scores badly on long-context retrieval. The obvious reading is
"this model is weak at long context." The real reading is that you ran it well outside the regime it
was trained in, and the serving stack had no reason to object.

**Mechanism.** Rope extension makes a long context *runnable*, not *learned*. Two models on the same
battery at 1M tokens:

| model | native training context | score at 1M |
|---|---|---|
| a 7B instruct model | 32K native | **0.31** |
| a 14B model actually trained at 1M | 1M | **0.65** |

The 7B is running in rope-extension territory at ~30x its native length and its retrieval collapses.
**Long-context training matters more than parameter count at long context**: which is exactly the
conclusion you would draw backwards if you attributed the gap to size.

There is a second, purely mechanical version of the same trap: the file you serve may have been
exported with a *reduced* extension factor, so the number your server enforces is smaller than the
number on the card. We hit a GGUF exported at YaRN factor 32 (`context_length = 262144`) for a model
whose upstream config is factor 128 over an 8,192 base (`max_position_embeddings: 1048576`). The
server hard-caps you to the file's value, verbatim:

> `the slot context (1048576) exceeds the training context of the model (262144) - capping`

Not a warning, an actual cap. Flags cannot raise it; only a metadata re-export can (no
requantization needed).

So there are three different numbers that all get called "context length", and they routinely
disagree:

1. what the **card** advertises (post-extension maximum),
2. what the **file or server** will actually allow (may be a reduced export),
3. what the model was **trained** at (the only one that predicts quality).

**Stacks and builds bitten.** Engine-independent. Observed on a long-context retrieval battery
across
two model families, and on GGUF exports of a rope-extended model.

**The check.**

1. **Read all three numbers before quoting a long-context result.** `config.json`
   `max_position_embeddings` and the rope factor; the served file's own `context_length` metadata;
   and the model card's stated *training* context, which is usually in prose rather than in config.
2. **Anchor with a shorter-context control.** Run your battery at the model's native length as well
   as at the long length. A model that scores well at native and collapses at 8x native is telling
   you about extension, not about capability.
3. **Include a model that was genuinely trained long** in any long-context comparison. Without one,
   every result is confounded with extension quality.

**The fix.** State the training context next to every long-context number, and never compare a
rope-extended model against a natively-long one without labelling which is which. If you need the
advertised length from a reduced export, re-export the GGUF metadata with the upstream
`context_length` and rope factor, then re-check memory, because the KV footprint at the advertised
length is frequently the *real* limit anyway (one stack allocated full-size KV for all 48 layers
even
though 36 were sliding-window with a 512 token span, ~104 KiB/token at f16, which wedged a 128 GB
box
into swap at 256K).

**Found.** 2026-05 (retrieval battery) and 2026-07 (the reduced-export cap).

**Attribution.** TheTom.

**Related, and it shares this entry's subject without duplicating it.**
[Trap 61](61-advertised-window-fails-silently.md) is a first-party measurement
of the same class on a lane advertising 1M over a 64K trained base. It covers
the part this entry does not: that nothing anywhere in the request or the
response tells you the advertised number stopped being true, and that
degradation is not monotone in depth, so one passing measurement above the
trained length is a coin flip rather than a result. The two landed in the same
pass, and the maintainer entry was the one renamed when they collided on a
title, because the framing here came first.

