# Trap 01: the reasoning field has two names

**Symptom.** Your thinking firing rate reads **0%** while the model is
visibly reasoning. Worse, it reads 0% *consistently*, which looks like a
clean finding rather than a bug. Any harness that also uses reasoning length
as a signal silently loses that signal too.

**Mechanism.** OpenAI-compatible servers expose the model's reasoning on
either `message.reasoning_content` or `message.reasoning` (and in streaming,
`delta.reasoning_content` or `delta.reasoning`), and some expose only one.
A harness that reads only the missing one parses every response as
"no reasoning".

**Stacks and builds bitten.** Five surfaces across three separate tools. A
vLLM lane serving Qwen 3.6 NVFP4 that exposes **no `reasoning_content` key at
all**; a community spine-probe runner whose reasoning column read 0 on all 42
rows; a third stack whose "0% fired" could not be distinguished from "was not
parsed" until the field was checked directly; and then two thinking-probe
scripts in the same upstream toolkit that still read only the one field.
Those two are the sharpest case, because their entire job is to measure
whether a model reasons: on a vLLM lane one would have reported
`NO_REASONING` in every arm, and the other would have shown a persona gate as
perfectly effective *including in its own control cell*. Both are fabricated
results that look like findings. Wire-level measurement on Laguna S 2.1
NVFP4 (vLLM 0.25.1) confirmed the streaming variant: reasoning arrives as
`delta.reasoning`, not `delta.reasoning_content` (@quantumleap68).

The generalization worth carrying: this is not a bug that happened to some
scripts, it is a property of **any tool that reads a reasoning field**. Audit
all of them at once, not just the one that surfaced the problem.

**The check.** Read **both** keys, and fall back to scraping `<think>` tags
out of `content`:

```python
reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
```

Then confirm positively: send one prompt you are confident makes the model
think, and assert the field is non-empty. An empty field means *wrong key* at
least as often as it means *did not reason*.

**The fix.** The snippet above, applied to every reasoning-reading tool in
your stack at once, plus the positive-control assertion in your preflight.

**Found.** 2026-07-26, cross-model gate study and spine-probe runs.

**Attribution.** Blackwellboy (lab runs); streaming-field confirmation by
@quantumleap68. Raw data:
[cross-model/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/cross-model)
and
[spine-probes/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/spine-probes).
