# Playbook: before you publish an A/B

You have two arms and a delta. This is the list to work through before the
delta becomes a number anyone else reads. Ten steps, in order. Each names the
entry it guards against.

Nothing here is new. Every step is a published entry, sequenced.

The framing that saves the most time, from
[trap 54](../traps/evaluation/54-run-order-and-warm-cache-artifacts.md):
**an outsized improvement is a bug report until proven otherwise.** If the
number moved more than your change plausibly explains, work the list in the
order below rather than writing it up.

---

## 1. Measure your own agreement floor first

**Guards:** [trap 35, identical weights do not score identically](../traps/evaluation/35-identical-weights-do-not-score-identically.md) (**Core**)

Run the same model twice, on the machines or sessions you actually intend to
compare across, on the same items, and report **per-item agreement**, not just
the score:

```python
agree = sum(a["correct"] == b["correct"] for a, b in zip(run1, run2))
print(f"{agree}/{len(run1)} item agreement, score delta {mean_a - mean_b:+.2%}")
```

Our own measurement of this floor is published: pooled **97.58%** item
agreement between identical runs, with cross-machine pairs straddling the
within-process pair, so machine identity was not the dominant variable
([the data note](../mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md)).
The calibration that came out of it, and its scope: plus or minus **1.3
points at n=600** for MMLU-style paired comparisons, and explicitly **not**
transferable to binary-outcome results.

**Stop condition.** Any effect smaller than your own floor needs a
same-machine paired re-run before it is publishable.

## 2. Fix one machine and one session as the measurement room

**Guards:** [trap 35](../traps/evaluation/35-identical-weights-do-not-score-identically.md)

Run every arm there, serially. Where a cross-machine comparison is
unavoidable, state both hosts next to the number and treat the agreement
floor as your minimum detectable effect. Necessary but, on our own
measurement, **not sufficient**: designating one evaluation machine removes a
variable that turned out not to be the dominant one.

## 3. Diff every request parameter between the arms

**Guards:** [trap 17, per-arm recommended sampling](../traps/evaluation/17-per-arm-recommended-sampling-confound.md) (**Core**)

List every request parameter that differs. If that list is not exactly the
variable under test, either fix the parameters or state the comparison as
"shipped-defaults versus shipped-defaults", which is a **different claim**
than "X versus Y".

Two adjacent checks belong here:

- If the checkpoint ships no `generation_config.json`, your server's built-ins
  silently became "the model's settings"
  ([trap 21](../traps/versioning/21-no-generation-config-server-defaults-win.md)).
  There is no such thing as "at model defaults" on that checkpoint.
- Send the thinking kwarg **explicitly** on every arm and pin the revision.
  The default drifts between revisions and uploads
  ([trap 03](../traps/reasoning/03-enable-thinking-default-drift.md), **Core**).

## 4. Ask whether anyone would serve your baseline

**Guards:** [trap 34, the baseline you degraded yourself](../traps/evaluation/34-baseline-you-degraded-yourself.md)

Write down the configuration of the reference arm and ask the one question:
would anyone serve this? If not, it is a handicap, not a floor. Name the
shipped default for every knob you touched, and if your reference differs on
any of them, add a third arm at the default and report against that too.

## 5. Report truncation rates per arm, and refuse to compare if they differ

**Guards:** [trap 36, the token cap is a per-arm handicap](../traps/evaluation/36-token-cap-is-an-arm-level-handicap.md)

```python
assert trunc_rate < 0.02, f"{trunc_rate:.0%} truncated: score by logprob, not generation"
assert abs(trunc_rate_a - trunc_rate_b) < 0.05, \
    f"cap binds unequally: {trunc_rate_a:.0%} vs {trunc_rate_b:.0%}"
```

Score multiple choice by logprob, never by generation, whenever the model
reasons. For generative benchmarks, set the cap from the longest-reasoning
arm's distribution and verify afterwards that it stopped binding.

## 6. Bucket on extractable output, then split by finish_reason

**Guards:** [trap 16, finish_reason is not a failure signal](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md) (**Core**) and [trap 12, empty content at a token ceiling](../traps/evaluation/12-empty-content-at-token-ceiling.md) (**Core**)

Never map `finish_reason` directly to pass or fail. A cap-hit can carry usable
content and a clean stop can carry none. Where empties cluster at the ceiling,
re-run only those at a larger budget before concluding anything about
capability, and inspect the tail before raising anything, because honest
truncation and degeneration look the same in an aggregate.

## 7. Assert the tokenized length of every benchmark prompt

**Guards:** [trap 49, the prompt does not tokenize to the length you named](../traps/evaluation/49-prompt-not-tokenized-to-target.md)

Assert the tokenized length, not the string length, and log the server's own
count. The tell that caught it for the finder: a KV-cache offset reading
**801** after a run labelled "4096 context". Anywhere your harness can observe
a real token count (cache offset, server `n_tokens`, `usage.prompt_tokens` on
a cold request) assert it against the target rather than printing it. Record
the achieved count next to the nominal one; if they differ by more than a
couple of percent the row is invalid, not caveated.

## 8. Counterbalance the order, discard warm-up explicitly, and run the null build

**Guards:** [trap 54, run order and cache artifacts](../traps/evaluation/54-run-order-and-warm-cache-artifacts.md)

1. Run A then B, and B then A. If the winner is whichever ran second, you have
   no result.
2. Fixed warm-up count, then an N-run median. Then check the warmed runs are
   stable: monotonic degradation across them is thermal throttling, a
   different artifact with the same shape.
3. **Test the null.** Run the improved configuration on a build that does not
   contain the improvement. Cheapest disproof available, and the one that
   settled the finder's case.

## 9. Gate the performance number on a correctness artifact from the same binary

**Guards:** [trap 52, the fast configuration was fast because it was wrong](../traps/evaluation/52-speed-measured-on-a-broken-config.md)

Same binary, same flags, same session. Not a correctness run from last week on
a different build. Minimum viable gate in order of cost: a coherence probe
plus a **discriminative** probe (a decimal comparison catches subtle breakage
that a capital-city question passes), then top-1 rank of a known answer rather
than readability of the output, then perplexity or KL against a
high-precision reference on the same build.

"It got faster and nothing broke" is not a report. "It got faster and here is
the probe output from the same build" is.

## 10. Record the unit under test, and check the log describes the lane you are on

**Guards:** [trap 09, same weights, three images, three outcomes](../traps/runtime/09-image-choice-changes-outcome.md), [trap 10, the quant label is not the kernel path](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) (**Core**), [trap 53, the config edit never took effect](../traps/runtime/53-config-edit-never-took-effect.md) (**Core**)

The unit under test is **image plus weights plus hardware plus build**, never
"the model". Pin the image by digest and record it next to the result.

Then stop trusting the launch command and interrogate the process that is
answering. After every restart, prove three things: what is holding the port
and when it started (a start time older than your edit means it never
restarted), whether the replacement failed to bind, and whether the **live**
server reports the setting you changed. Kill by port, not by process-name
substring.

Two log-reading corollaries, both published:

- A label in `config.json` establishes what the checkpoint **is called**, not
  the kernel path the engine took. Only a runtime tell settles that: the
  engine's backend-selection log, decode throughput against an f16 baseline,
  or utilisation against power draw
  ([trap 10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md)).
- The most alarming line in a startup log is often a step, not a failure. Read
  what came **after** it, and do not let a health check grep for the alarming
  string ([trap 76](../traps/runtime/76-device-rejection-log-line-is-not-fatal.md)).

## Before the lane counts as up at all

Readiness is a completed generation, not an endpoint answering. `/v1/models`
responds when the HTTP server binds, which is well before weights are
resident. Details and the two things it has already cost:
[doctor/README.md](../doctor/README.md#readiness-is-a-completed-generation-not-an-endpoint-answering).

---

**Related playbooks.** [Porting a harness to a new server](porting-a-harness.md)
if either arm runs on a stack you have not measured before.
[Long context looks broken](long-context-looks-broken.md) if either arm is a
long-context result.
