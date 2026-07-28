# Trap 44: within one model and one task, reasoning length is right-skewed, so no fixed ceiling closes the empty tail

**Found by TheTom.**

**Status: reproduced here** (two sizes of one family, same battery, same ceiling). Raw is per-turn
JSONL held outside the tree; can be produced on request, per the default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo).

**Relationship to [trap 12](12-empty-content-at-token-ceiling.md) and
[trap 22](22-family-card-budget-floors-differ-by-size.md).** Trap 12's 2026-07-28 correction already
retracted the universal ceiling and replaced it with a five-step procedure, and step 4 tells you to
establish the floor as a distribution for **this** model and **this** task. This entry supplies the
mechanism underneath that step, and the automated form of step 3: the distribution has a right tail
that any fixed ceiling truncates, so re-running affected items at a larger ceiling is a loop rather
than a one-shot fix.

If a maintainer would rather fold this into trap 12 as a step 3 amendment plus a data point on trap
22, that is a better outcome than a separate entry and I will not argue for the entry.

**Symptom.** You work through trap 12's procedure, establish a per-model floor, re-run the affected
items, and confirm they convert. A full battery run at that same floor still returns a few percent
empty. Because the rate is now small it reads like a rare genuine behaviour rather than a residual
artifact, and it gets scored as one.

**Mechanism.** Reasoning length at `temp > 0` is stochastic and right-skewed. The same prompt on the
same model rolls 2,100 tokens of thinking one time and 2,600 or more the next. So the per-model,
per-task floor from trap 12 step 4 is a property of the **distribution**, and a single number drawn
from it (median, or the value that converted your sample) still truncates everything in the tail
beyond it.

Two consequences that do not follow from the per-model and per-family framing on their own:

1. **Raising the ceiling moves the cliff without removing it.** On a roughly 90 scenario battery,
   after raising the ceiling to 5120, **9.1% of turns were still empty**. Trap 12's own body already
   records a model where budget does not convert at all; this is the weaker but more common case,
   where budget converts most and leaves a tail.

2. **The asymmetry punishes smaller models, which is a second data point for trap 22.** Fatter tails
   on smaller or less distilled models mean a ceiling calibrated on a large sibling manufactures
   phantom failures on the small one, in exactly the direction that reads as a plausible capability
   finding. Different pair and different battery from trap 22's:

   | model | empty-final rate at `max_tokens=2560` |
   |---|---|
   | Qwen3.5-9B | **26%** |
   | 35B-A3B sibling | **2.7%** |

   Probing one 9B empty: `finish_reason=length`, all 2,560 tokens inside the reasoning block, still
   mid-thought, non-degenerate tail. The same prompt at 5120 finished naturally in 2,146 tokens with
   a clean answer, so the median was never the problem.

**Stacks and builds bitten.** Engine independent; any OpenAI compatible endpoint serving a model
that
emits `<think>` blocks or a separate `reasoning_content`. Measured on Qwen3.5-9B against a 35B-A3B
sibling at temp 0.6, top_p 0.95, roughly 90 scenarios plus long-running probes.

**The check.** Send the same prompt N times at your chosen ceiling and read the **distribution**
rather than one sample. A pileup at exactly the cap is the signature:
[`checks/reasoning_budget_probe.py`](../../checks/reasoning_budget_probe.py)

```
$ python3 checks/reasoning_budget_probe.py --base-url $URL --model $M --max-tokens 2560 -n 20 --temp 0.6
  truncated (finish_reason=length): 5/20 = 25.0%
  completion_tokens p50/p90/max: 1840 / 2560 / 2560
  runs landing exactly at cap: 5
```

Run it at your real eval temperature. At temp 0 you will not see the tail that bites you at 0.6.

Order matters here: trap 12 step 1 (is there extractable output) and step 2 (is the tail degenerate)
come first. This probe is only meaningful once you know you are looking at honest truncation.

**The fix.** Mechanise trap 12 step 3 as **retry-on-truncation** inside the harness rather than as a
manual re-run. On `finish_reason == "length"`, or on empty content with a non-degenerate tail,
re-request the same turn with an escalating ceiling (4096, then 8192, then 16384) up to a hard cap.
Every captured final is then a completed answer, and a true empty (`finish_reason == "stop"` with no
extractable content) becomes real signal.

Record `finish_reason`, `completion_tokens` and `retries` per turn, and report converted against
non-converted with the ceiling beside every score, which is trap 12 step 5 and unchanged by any of
this.

Two operational notes from applying it across a suite:

- **Audit every runner, not only the main one.** One scorer in our harness had a fixed
  `max_tokens=1024` and no retry ladder while every other runner had one. A verbose step by step
  answer was cut off before stating its result and scored as a wrong answer on a math gate. After
the
  same escalating retry was added, all four model variants scored cleanly, and the 2048 rung was
  needed on three of the four re-runs, so the exposure was real and would have recurred silently at
  every future tier.
- **A fixed mid cap is the worst of the three options.** In a three arm thinking ablation (off,
  capped at 2048, on-full, temperature held fixed), the capped arm was dominated by truncation
  empties, 15% on the behavioural battery and 56% on long-running probes, making it strictly worse
  than thinking off. If retry is not available, turning thinking off beats capping it.

**Found.** 2026-06, when a smaller model's empty rate was about to be written up as an over-refusal
finding.

**Attribution.** TheTom. Traps 12 and 22 are Blackwellboy's; this entry adds the within-model
variance mechanism, the automated form of step 3, and a second per-size data point.
