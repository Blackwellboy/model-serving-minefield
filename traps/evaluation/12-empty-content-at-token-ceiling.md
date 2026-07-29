# Trap 12: valid requests return empty content at a token ceiling, and whether budget converts them is a per-model, per-task property

**Found by Blackwellboy.**

**Status: reproduced here** (40-cell budget map, published raw).

**Symptom.** A reasoning model returns HTTP 200 with **empty content** on
hard tasks. It looks like a capability collapse, scores as a zero in any
harness, and produced a real cross-model anomaly in our published numbers
(a 1/16 intelligence score that was actually this).

**Mechanism.** With thinking on and a low `max_tokens`, the model spends the
entire budget inside the reasoning block and the answer never starts. The
tail is ordinary mid-task reasoning, not a loop. Raising the budget converts
the failures completely: the task that returned empty content **28/30 at a
4096 ceiling converts to 10/10 valid answers at 8192** and stays 10/10 at
12288 and 16384. Reasoning demand plateaus (~5.2 to 5.7K tokens median on
that task); it does not grow to fill the budget. Raw and writeup:
[qwen-ceiling](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/qwen-ceiling).

The same ceiling produces a different signature on a different model
(degeneration loops with zero extractable code, where budget does NOT fix
it), which is trap 16's bucketing lesson: the response to a cap-hit is a
model property you must measure, not assume.

**Stacks and builds bitten.** Qwen 3.6 35B-A3B NVFP4 on vLLM (GB10), first
seen as 28/30 empties in a cross-model grid at 4096, replicated 8/10 in the
budget map, converted at 8192.

Reproduced on mlx_lm (2026-07-27, stock server, prism-ml
Ternary-Bonsai-27B-mlx-2bit, Apple silicon): a hard task with thinking on
at max_tokens=512 returned HTTP 200, finish_reason=length, no content, and
1,484 chars of reasoning; a degeneration screen read the tail as honest
truncation (unique-line ratio 1.00, zlib ratio 0.53). The MLX flavor of the
signature differs: where vLLM returns `content` as an empty string, mlx_lm
OMITS the `content` key entirely, so `msg["content"]` raises KeyError on
every cap-hit. A KeyError storm that correlates with
`finish_reason=length` is this stack's version of the symptom, and it is
easy to misread as a client bug instead of a budget artifact (see
[trap 01](../reasoning/01-reasoning-field-two-names.md) for the absent-key
shape). Budget note: the same 27B-class model converted a short arithmetic
answer in 225 completion tokens with thinking on and burned all 512 on the
hard task without converting, so the thinking-on conversion floor sits
somewhere above 512 on that lane; per
[trap 22](22-family-card-budget-floors-differ-by-size.md), find it for THIS
model rather than borrowing a family number. The upstream guide ecosystem adopted the
lesson as "an empty response at a token cap is a failure, not a truncation"
([offlabel patterns.md](https://github.com/TheTom/offlabel/blob/main/patterns.md)).

**The check.** Bucket every scored zero by "was content empty at a cap-hit".
If empties cluster at the ceiling, re-run only those at a larger budget
before concluding anything about capability.

**The procedure.** There is no single ceiling that makes this go away. Work
through it in order:

1. **Check for extractable output before calling it empty.** A cap-hit can
   still carry usable content, and a clean stop can carry none. Bucket on
   what you can extract, not on `finish_reason`
   ([trap 16](16-finish-reason-is-not-a-failure-signal.md)).
2. **Inspect the tail before raising anything.** Honest truncation and
   degeneration look identical in the score and need opposite responses.
   Screen the reasoning tail (unique-line ratio, compression ratio): a
   non-degenerate tail means budget is plausibly the fix, a looping tail
   means budget will not help and a larger ceiling only costs more.
3. **Re-run only the affected items at a larger ceiling.** Do not re-run the
   whole suite; the comparison you want is same-item, two ceilings.
4. **Establish the floor as a distribution for THIS model and THIS task**,
   not as a number borrowed from a family card. Budget floors vary by
   multiples between sizes of one family
   ([trap 22](22-family-card-budget-floors-differ-by-size.md)).
5. **Report both the converted and the non-converted cases**, with the
   ceiling next to every score. "N of M converted at ceiling C" is the
   honest result; a single post-fix number hides the ones that never came
   back.

**Correction, 2026-07-28.** This entry previously prescribed a fix: "give
thinking-on reasoning models a ceiling of at least 8192". That was a
universal number generalised from one model on one task, and this registry
contradicts it in two places. Trap 22 measures three members of one family
and finds three different floors, one of which is above 8192, so a reader
who sets 8192 and moves on still gets empty content. Trap 16 shows that
"empty at a cap-hit" is not even the right bucket, because cap-hits can
carry usable output and clean stops can be empty. This entry's own body
already recorded a model where raising the budget does NOT convert the
failures. The number has been replaced by the procedure above. No measured
claim in this entry changed.

**Found.** 2026-07-26 (grid anomaly and budget map).

**Attribution.** Blackwellboy.

## Added 2026-07-28: a measured floor, and proof there is no safe one to copy

**NVIDIA Nemotron 3 family, three checkpoints (Nano 30B A3B NVFP4, Nano Omni 30B A3B NVFP4, Super 120B A12B NVFP4), GB10-class single nodes, vLLM 0.20.0 and 0.25.1.** Confirmed on all three, with a fully crossed sweep on the 120B
member. Three samples per cell, two task difficulties, seven budgets from 64 to
4096:

| Thinking | Task | Floor for non-empty content |
|---|---|---|
| on | easy | 64 tokens (already 3/3 at the smallest budget tested) |
| on | hard | **between 64 and 128**: 0/3 at 64, 3/3 at 128 |
| off | easy | never empty at any budget |
| off | hard | never empty at any budget |

**Thinking off was immune.** Across every budget and both difficulties the
thinking-off arm never produced empty content. If your workload tolerates
thinking off, this trap does not apply to you, and that is a measured result
rather than an assumption.

**But there is no floor to copy, and this is the part to take away.** The
sweep's hard task converted at 128 tokens; the registry doctor's harder probe on
the same lane still returned empty at 512 with 2007 characters of honest
reasoning (unique-line ratio 1.00, zlib 0.49, so it was thinking rather than
degenerating). The budget you need is a function of how long the model chooses
to think, which is a function of the task. Do not lift a number out of that
table into production.

**It also fires with media attached**, on the multimodal member: 501 prompt
tokens for an image, 24 completion tokens, `content` null. Any harness that
scores an image task zero on a small budget is measuring its budget.

There is a shipped rescue on one member of this family, and it is a kwarg the
template never reads: see
[trap 65](../reasoning/65-parser-only-rescue-kwarg.md).

*Status of this addendum: measured here, raw not published.*

## Added 2026-07-28: why the floor has to be a distribution, not a number

**Found by TheTom** ([PR #1](https://github.com/Blackwellboy/model-serving-minefield/pull/1)),
folded here at his suggestion rather than landing as its own entry. **Status:
contributor-measured, conditions as reported.** Measured on Qwen3.5-9B against a
35B-A3B sibling, temperature 0.6, top_p 0.95, roughly 90 scenarios plus
long-running probes; his raw is per-turn JSONL held outside the tree.

This is the mechanism underneath step 4 above, and it is the reason the table in
the previous section is a set of observations rather than a lookup.

**Reasoning length at `temp > 0` is stochastic and right-skewed.** The same
prompt on the same model rolls 2,100 tokens of thinking one time and 2,600 or
more the next. So the per-model, per-task floor is a property of the
**distribution**, and any single number drawn from it (the median, or the value
that happened to convert your sample) still truncates everything in the tail
beyond it.

Two consequences that do not follow from the per-model and per-family framing on
their own:

1. **Raising the ceiling moves the cliff without removing it.** On a roughly 90
   scenario battery, after raising the ceiling to 5120, **9.1% of turns were
   still empty**. This entry already records a model where budget does not
   convert at all; this is the weaker and more common case, where budget
   converts most and leaves a tail. Because the residual rate is small, it reads
   as a rare genuine behaviour rather than a residual artifact, and it gets
   scored as one.
2. **A fixed mid cap is the worst of the three options.** In a three-arm
   thinking ablation (off, capped at 2048, on-full, temperature held fixed), the
   capped arm was dominated by truncation empties, 15% on the behavioural
   battery and 56% on long-running probes, making it strictly **worse than
   thinking off**. If retry is not available, turning thinking off beats capping
   it.

**The check, at your real eval temperature.** Send the same prompt N times at
your chosen ceiling and read the **distribution** rather than one sample. A
pileup at exactly the cap is the signature:

```
  truncated (finish_reason=length): 5/20 = 25.0%
  completion_tokens p50/p90/max: 1840 / 2560 / 2560
  runs landing exactly at cap: 5
```

At temperature 0 you will not see the tail that bites you at 0.6. Order still
matters: steps 1 and 2 come first, because this probe is only meaningful once
you know you are looking at honest truncation and not degeneration.

**The fix: mechanise step 3 as retry-on-truncation** inside the harness rather
than as a manual re-run. On `finish_reason == "length"`, or on empty content
with a non-degenerate tail, re-request the same turn with an escalating ceiling
(4096, then 8192, then 16384) up to a hard cap. Every captured final is then a
completed answer, and a true empty (`finish_reason == "stop"` with no
extractable content) becomes real signal.

**Audit every runner, not only the main one.** One scorer in his harness had a
fixed `max_tokens=1024` and no retry ladder while every other runner had one. A
verbose step-by-step answer was cut off before stating its result and scored as
a wrong answer on a math gate. After the same escalating retry was added, all
four model variants scored cleanly, and the 2048 rung was needed on three of the
four re-runs, so the exposure was real and would have recurred silently at every
future tier.

*A runnable probe for this ships with his PR and is held pending a separate
review against the [check contract](../../CONTRIBUTING.md#the-contract-which-is-enforced-mechanically);
the assertion above is the payload and does not need the script.*

## Added 2026-07-28: confirmed on Ollama, exactly as described

**Ollama 0.32.5, `qwen3:8b`, GB10 aarch64 CUDA 13.** At `num_predict` 16 and at
64: `done_reason: "length"`, `content` empty, and the reasoning field populated.
That is this entry's mechanism on a stack it had not been recorded on, with
nothing new to add, which is why it is a stack line rather than an entry.

Two Ollama-specific notes that keep it from being confused with its neighbours:

- The out-of-range **context** request produces the same response shape for a
  different reason, and a bigger budget makes it worse rather than better. That
  is [trap 79](../memory/79-out-of-range-context-request-accepted.md).
- A streamed request at `max_tokens` 512 sent 511 **empty content deltas** on
  this stack before content appeared at 4096. That is this entry wearing a
  different hat, not an independent channel-routing finding, and it is recorded
  that way deliberately: calling it channel routing would have been wrong.

*Status of this addendum: reproduced here. Freely obtainable stack, two requests.*

## Added 2026-07-28: reproduced on SGLang

**SGLang 0.5.16, Laguna S 2.1 NVFP4 on DGX Spark GB10.** The doctor's hard
task returned HTTP 200 with `finish_reason=length`, empty content and 569
characters of reasoning at `max_tokens=512`. Its one-sample degeneration
screen read as honest truncation (unique-line ratio 1.00, zlib ratio 0.34).
This establishes the cap-hit shape on the stack; it does not establish a
conversion floor.

*Status of this addendum: contributor-measured, conditions as reported, by
[@newageinvestments25-byte](https://github.com/newageinvestments25-byte). Exact
conditions and the complete doctor coverage line are in the
[SGLang DGX Spark field note](../../mining/2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md).*
