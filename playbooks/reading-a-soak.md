# Playbook: reading a soak

A soak runs one configuration for hours and asks whether it degrades. There is
no second arm, so every guard in
[before you publish an A/B](before-you-publish-an-ab.md) that relies on a
comparison is unavailable to you. What replaces them is arithmetic discipline
about the aggregate you are reading.

The failure this playbook exists to prevent: **a soak reports a falling
acceptance rate, and the fall is entirely an artifact of which requests
happened to be in each bucket.** We produced exactly that, measured it, and the
numbers below are ours.

Method credit: the weighted-aggregate reasoning is
[Hikari's per-domain evaluation discipline](https://github.com/hikarioyama/Hikari-knowledge)
(`nodes/methodology/per-domain-eval-discipline`), applied here to a time axis
rather than a domain axis. His node states the general form: an aggregate is a
weighted average, and a dominant category can move it while the components do
not. The soak-specific consequences below are ours.

---

## 1. Know which of the two acceptance numbers you are quoting

There are two, they are both correct, and they are not the same number.

| Estimator | Formula | Who reports it |
|---|---|---|
| **Pooled**, draft-weighted | `sum(accepted) / sum(draft_tokens)` | every engine's cumulative counter |
| **Mean of ratios**, request-weighted | `mean(accepted_i / draft_tokens_i)` | almost every hand-written soak reporter |

They differ whenever acceptance correlates with drafts per request, which it
always does, because the request families that draft the most are rarely the
ones that accept the most.

On one of our own 1.93-hour soaks, same 48 requests, same raw counters:

```
pooled draft-weighted   0.5730
mean of per-request     0.6288
                        ------
gap                     5.58 points
```

**A published acceptance figure taken from an engine's cumulative counter is the
pooled one.** If your soak reporter prints the mean of ratios and you compare it
against that published figure, you are comparing two different estimators and
some of your gap is arithmetic. Fix the estimator before you interpret the gap.

```python
pooled = sum(r["d_accepted"] for r in ok) / sum(r["d_draft_tokens"] for r in ok)
```

## 2. Never read drift off the pooled series

This is the important one.

Pooled acceptance is weighted by draft tokens. Round-robin request scheduling
equalises **request counts** per family, which is what most soak runners are
built to do, and it does not equalise **draft-token counts**, which is what the
pooled ratio actually weights by. So the guard does not bind on the metric you
are reading.

Our soak, by half-hour bucket:

| bucket | n | pooled | mean of ratios | standardised |
|---|---|---|---|---|
| 0.0h | 13 | 0.6081 | 0.6740 | 0.5739 |
| 0.5h | 26 | 0.5725 | 0.6262 | 0.5774 |
| 1.0h | 9 | 0.5239 | 0.5712 | 0.5896 |

**Pooled falls 8.4 points. Standardised rises 1.6 points.** Same requests, same
counters, opposite conclusions.

The cause is one family's weight, not any family's behaviour:

| family | draft-token share 0.0h | 0.5h | 1.0h | its own acceptance |
|---|---|---|---|---|
| multi_turn | 16.5% | 36.8% | **61.6%** | 0.43, and flat |
| code_gen | 17.4% | 10.2% | 8.5% | 0.82 |
| math_reasoning | 21.6% | 14.3% | 13.0% | 0.70 |

`multi_turn` has the lowest acceptance of any family and it grows from a sixth
to nearly two thirds of all draft tokens. Meanwhile, within themselves, six of
the seven families with usable coverage were **flat or rising**: code_gen +10.7
points, short_qa +12.5, math_reasoning +7.6, burn_canary +5.2, multi_turn −0.9,
summarization −4.7. The pooled decline is a mix shift wearing a drift costume.

**The fix is direct standardisation.** Hold the family weights fixed at the
whole-run mix and recompute each bucket:

```python
w = {f: draft_tokens[f] / total_draft_tokens for f in families}   # fixed weights
standardised = sum(w[f] * rate_in_bucket[f] for f in families_present) \
             / sum(w[f] for f in families_present)
```

If you report only one drift number, report that one. If you report two, report
the per-family series and let the reader see the components.

## 3. Bucket by complete cycles, not by wall clock

A round-robin runner emits families in a fixed cycle. Bucketing by half-hour
cuts the final cycle wherever the clock lands, so partial buckets have
unbalanced family composition **by construction**, independently of anything the
server did.

Our final bucket held 9 requests against a 9-family cycle, and its composition
was `multi_turn=2, summarization=2, thinking_on=0, translation=0`. That bucket
is not a sample of the workload. It is a fragment of one cycle.

Bucket on completed cycles. Then every bucket has identical family composition
and the mix problem in step 2 cannot arise at all. Discard the trailing partial
cycle rather than reporting it.

## 4. Put the drift instrument outside the workload mix

The only request family that can carry a clean drift signal is one that is
**identical every time**: same prompt, temperature 0, same token budget. Ours is
a fixed canary, and it is the right instrument, but it was 2.5% of draft tokens
and 6 requests across the run.

Give the canary enough weight to say something. It costs almost nothing, it is
immune to every mix effect in this playbook, and it is the one series where a
change is unambiguously the server rather than the workload. Track its output
hash too: a canary that changes what it says is a stronger degradation signal
than one that changes how fast it says it.

## 5. Size the run before you claim a trend

48 usable requests over 1.93 hours, 9 in the final bucket, 4 to 6 per family, is
not a drift measurement. It is a smoke test that the lane survives two hours.

Say which one you ran. A soak that reports "no degradation over N hours" with
single-digit per-bucket counts has demonstrated that the lane stays up, which is
worth knowing and is not what the sentence claims.

## 6. Acceptance is content-dependent, so a bare acceptance number means nothing

Across families in our soak, pooled acceptance ranged from **0.43** (multi_turn)
to **0.82** (code_gen). A 39-point spread on one model, one build, one session.

This means two things:

1. **Any acceptance figure must carry its workload.** "67.33% acceptance" is a
   property of a model and a benchmark mix jointly. Quoting it against a
   different mix is not a comparison.
2. **A gap between two acceptance figures is not evidence of degradation until
   the mixes are matched.** A twelve-point gap sits comfortably inside a
   39-point family spread. Reweight one workload to the other's mix, or compare
   family by family, before reaching for a drift or regression explanation.

## 7. Separate the estimator, the mix and the model before you attribute anything

In order, cheapest first:

1. Recompute both estimators on your own raw (step 1). Some of the gap is arithmetic.
2. Standardise to a fixed mix (step 2). Some of the rest is composition.
3. Compare family by family (step 6). What survives is the model.

Only what survives all three is a property of the serving stack.

---

**Related.** [Before you publish an A/B](before-you-publish-an-ab.md) for the
two-arm case, and its replicate standard, which a soak cannot satisfy and must
therefore not imply.
