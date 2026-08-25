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

**Your floor is not a constant, and temperature 0 does not remove it.** On a
multi-slot server, byte-identical replies to a repeated temperature-0 request
depend on three things the usual check does not vary: concurrency above 1, a
prompt above a length floor that a minimal reproduction sits below, and the GPU
architecture. Measured on one build, 108-token prompts never diverged in 256
concurrent responses and 220-token prompts diverged in 74 of 256
([trap 91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md)),
and at 444 tokens and above the same binary and weights diverged on `sm_120` and
not at all on `sm_86`
([trap 94](../traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md)).
Measure the floor at the prompt length and concurrency you will actually run,
on the card you will actually run, and compare hashes rather than eyeballing a
sample: the divergences were all fluent, correct, semantically different
sentences.

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
- **Hash the rendered prompt per arm** when the variable under test is a
  reasoning or system-text control. Card-style prose such as
  `Reasoning strength: low` can leave the template default high in place and
  produce a dual directive while only `chat_template_kwargs` binds the Jinja
  variable ([Muse Glimmer 30B note](../mining/2026-08-11-muse-glimmer-30b-reasoning-control-and-stack.md)).
  Preserve the full request body and render SHA next to every scored row.
- **Extract only final `content` for code/answer scoring.** Never execute or
  score `reasoning_content` as the answer. Content-only consumers can also
  look blank while reasoning streams
  ([trap 23](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md)).

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

   **The replicate standard: three, of whatever unit actually carries your
   variance.** Two replicates tell you whether the arms agree in direction.
   They cannot tell you how far apart replicates of the *same* arm normally
   sit, because two points have one degree of freedom and no usable spread.
   Three is the smallest number that estimates its own noise.

   The unit is not always a sampling seed. Identify what your variance
   actually rides on and replicate *that*:

   | Design | Replication unit |
   |---|---|
   | Sampled decoding, temperature above 0 | sampling seed |
   | Greedy or logprob-scored, load-time property under test | **server restart** |
   | Cross-machine claim | machine, then restart within machine |

   Replicating seeds on a temperature-0 arm measures nothing, and replicating
   restarts on a sampled arm confounds two sources. Name the unit next to the
   count: "three restarts", not "three runs".

   **The one substitution we accept.** You may run two replicates instead of
   three if the variance estimate comes from a *dedicated* calibration measured
   under the conditions you are running, rather than from the two replicates
   themselves. Our agreement floor is that calibration. When you use it, say so
   explicitly and re-measure the floor inside the run as a check, which costs
   one extra arm per configuration and is what makes the substitution
   auditable. Two replicates with no external floor is a single-seed result
   with extra steps, and publishes as one.

   The adjacent trap: reporting an aggregate across replicates that were not
   the same configuration. Do not combine checkpoints, baselines, or transient
   snapshots under one percentage.
3. **Test the null.** Run the improved configuration on a build that does not
   contain the improvement. Cheapest disproof available, and the one that
   settled the finder's case.
4. **Restart the server between arms, and assert the cache is cold.**
   Counterbalancing the order is not enough on its own: on one measured build
   the prompt cache persisted across separate client invocations against a
   single process, retained prompts issued roughly a thousand requests earlier,
   and **reversed the sign** of a prefix-reuse result when the arms were re-run
   in the opposite order against that same process
   ([trap 92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md)).
   Both runs were internally consistent; one was measuring the other's history.
   Assert `cached_tokens == 0` on the first request after each restart. Setting
   `cache_prompt: false` is the wrong tool here, because it measures no reuse
   rather than clean reuse.

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

## 11. Name the layer that moved before naming the speedup

**Guards:** [trap 09](../traps/runtime/09-image-choice-changes-outcome.md),
[trap 52](../traps/evaluation/52-speed-measured-on-a-broken-config.md),
[trap 54](../traps/evaluation/54-run-order-and-warm-cache-artifacts.md),
[trap 134](../traps/evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md)

An end-to-end tok/s delta is not automatically a model speedup. Before you name
the winner, name **which layer moved**, and record the fields that make that
claim defensible.

### Required layer fields

**MODEL**

- checkpoint / revision
- artifact / weights digest
- correctness gate (same-build probe, not a stale run)

**SERVING_ENGINE**

- engine / build / image (prefer digest)
- endpoint / host identity for each peer under test (sanitized alias is fine)
- launch and request flags (or a normalized flags digest)
- actual ISL (tokenizer- or server-counted)
- actual OSL
- TTFT / prefill when relevant
- decode tok/s
- queue / concurrency
- speculative acceptance when speculative decoding is in play

**TRANSPORT**

- path class
- intended and **actual** interface
- path proof ([trap 134](../traps/evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md))
- bytes TX/RX where relevant
- transport wall where measurable
- host staging / directness if known

**END_TO_END**

- request wall
- time-to-finished-batch
- time-to-finished-task

### Claim ladder (maximum defensible class)

| Class | Defensible only when |
|---|---|
| **MODEL** | The model/artifact is the intended changed layer, and serving + transport conditions are held or controlled enough for that claim. |
| **SERVING_ENGINE** | Model and transport are held while serving implementation/config is the intended changed layer. |
| **TRANSPORT** | Model and serve configuration are held (including endpoint/host identity and engine revision), transport/path is the intended changed layer, and **path proof** is present. |
| **END_TO_END_COMPOSITE_ONLY** | Multiple layers changed, lower layers are unknown, or required attribution fields are missing. |

Missing evidence **lowers** the claim class. Absence never proves two arms were equal.

Offline metadata audit (no endpoint contact):
[`checks/benchmark_attribution_preflight.py`](../checks/benchmark_attribution_preflight.py)
with schema
[`docs/benchmark-attribution.schema.json`](../docs/benchmark-attribution.schema.json).
Doctor probes live endpoints; this checker only classifies claim defensibility
from the metadata you already have.

### Concrete lesson (sanitized FlashRDMA portable serving)

Across two campaign stages, observed end-to-end 8K median decode throughput
moved dramatically:

| Arm | Prior Wi-Fi session (tok/s) | Later wired session (tok/s) |
|---|---:|---:|
| Flash | 1.479 | 7.339 |
| TCP | 3.465 | 7.631 |

The later run changed **not only** physical path but also the Spark endpoint
and the upstream FlashRDMA revision. Therefore this cross-session pair is
deliberately classified as **`END_TO_END_COMPOSITE_ONLY`**. It must **not** be
cited as a pure transport, model, or serving-engine speedup. A plausible story
is not enough when more than one layer changed - that is the point of the
attribution contract.

A **within-session** wired cell remains a valid transport-implementation A/B
when endpoint, revision, fixtures, and path proof are held: on the later wired
session, tokenizer-exact 8K medians were TCP 7.631 vs Flash 7.339 tok/s (with
near-parity also at 1K/4K). Do not collapse that held A/B into the composite
cross-session table above.

### Native RoCE / GPUDirect claim boundary

Do **not** claim native RoCE or GPUDirect merely because:

- `mlx5` (or another RDMA device) exists on one endpoint,
- CUDA-managed memory is used,
- traffic is Ethernet,
- a setting or path class string contains "RDMA".

A native / GPUDirect claim needs positive path evidence such as: the actual
native backend selected, correct HCA/device, correct GID/path, direct
GPU-memory registration / dma-buf where applicable, NIC/RDMA counters, and
proof that host staging / fallback was **not** the executed path. Negative or
unproven evidence stays a claim boundary, not a new trap.

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
