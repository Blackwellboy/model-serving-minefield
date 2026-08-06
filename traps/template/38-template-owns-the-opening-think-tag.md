# Trap 38: the template supplies the opening think tag, so raw generations never have one

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-05 entry).**

**Status: reported by others.**

**Symptom.** You collect generations outside the chat endpoint (rejection
sampling, RL rollouts, an offline scorer, anything that builds the prompt
itself) and the pass rate is far below what the model demonstrably achieves
interactively. Inspecting the text, the reasoning is there and it is fine.
What is missing is the opening `<think>`: the output begins mid-thought and
ends with a `</think>`, so every parser looking for a balanced pair treats it
as malformed and every downstream filter drops it.

**Mechanism.** In this template family the opening `<think>` is emitted by
the **generation prompt**, not by the model. The assistant turn is opened for
the model with the tag already in place, so the model correctly never writes
it. That is invisible while you use the chat endpoint, because the template
put the tag in the prompt and your parser sees the tag in the rendered
conversation. The moment you assemble the prompt yourself and keep only the
completion, the tag is gone and the reasoning block is unbalanced.

This is the same root cause as trap
[02](02-orphaned-think-close-tag.md) seen from the other side. There, a
server-side parser strips the opening tag and leaves the close, so every
reply starts with a stray `</think>`. Here, nobody supplies the opening tag
at all. In both cases the invariant to hold onto is: **the model does not
own the opening tag, the template does.**

**Stacks and builds bitten.** Qwen3.6-35B-A3B, revision
`995ad96eacd98c81ed38be0c5b274b04031597b0`, in an offline rejection-sampling
and GRPO rollout pipeline (raw completions, prompt assembled by the trainer
rather than by an OpenAI-compatible endpoint). Any Qwen 3.5/3.6-family
template that opens the think block in the generation prompt is exposed, and
so is any pipeline that trains or scores on completions rather than on the
rendered conversation.

**The fix.** Prefill the assistant turn with the opening tag before you
generate, and re-attach it to the completion before you parse, score or
train:

```python
prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
prompt += "<think>\n"                    # prefill: what the chat path does for you
completion = model.generate(prompt)
text = "<think>\n" + completion          # recombine before parsing or training
```

Measured effect of adding the prefill, paired on the same prompts and scored
under the finder's lenient criterion: **+0.394, CI95 [+0.148, +0.647]**.
That is not a tuning delta, it is the difference between a pipeline that
works and one that does not.

The recombination half matters as much as the prefill. If you generate with
the prefill but train on the completion alone, the model is supervised on
text that starts mid-reasoning. The finder records prefill recombination as a
hard requirement of his GRPO setup for exactly this reason, and verified it
byte-for-byte.

**The check.** Take one generation from your offline pipeline and count the
tags:

```python
assert text.count("<think>") == text.count("</think>"), \
    "unbalanced think block: the template opened it, your pipeline dropped it"
```

Run it on the first rollout, not after the first training run. More
generally, before trusting any offline pass rate, render one conversation
through `apply_chat_template` with `add_generation_prompt=True` and read the
tail of the string. Whatever the template appends after the assistant header
is text your pipeline must reproduce.

**Found.** 2026-07-05, while diagnosing why offline rollout pass rates were
far below the model's interactive behavior. The finder's rollout set at the
time was 384 prompts at 8 samples each, with a lenient best-of-8 rate of
0.621 after the fix.

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who traced this to the template rather than to the model and published the
paired effect of the fix. Related: trap
[02](02-orphaned-think-close-tag.md) (the server-side mirror image) and trap
[25](25-empty-think-blocks-poison-prefix-cache.md) (what the template emits
for empty reasoning).
