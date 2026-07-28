# HF transformers `generate()` and accelerate placement

**Measured here:** no (seven entries name it and not one was measured here)


**7 entries name HF transformers or accelerate** in their evidence surfaces
(see [how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)).

**Not one of the seven was measured here on this stack.** Six come from
[@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b) and one from
TheTom, and the registry has never run a `generate()` workload of its own.
That is the honest state of this page, and it changes what you should do with
it: five of the seven are **reported by others**, one is
**contributor-measured, conditions as reported**, they are linked to the
finder's own published log, and none of them carries the "we ran it on this
stack" weight that the vLLM and llama.cpp pages carry. Read them as
well-documented reports from someone else's hardware.

The seventh needs its own sentence, because the status line alone would
mislead you here. Trap
[35](../traps/evaluation/35-identical-weights-do-not-score-identically.md) is
**reproduced here**, and it was reproduced on a **different build class**, not
on HF transformers. The class survived the port and got stronger in the
process, which is the useful fact; it is not first-party evidence about
`generate()`. The same qualifier applies to trap
[33](../traps/routing/33-moe-inference-topk-expansion-tax.md), whose
first-party confirmation is NVFP4 under vLLM while the finder's numbers are
bf16 here.

Almost all of this material arrived through **eval and research workloads**
rather than serving, which is what the stack is mostly used for: a library you
call in a loop, not a server you point a client at. So the traps cluster in
two places, placement and measurement, rather than in request handling.

## The three checks to run first

**1. After loading with `device_map="auto"`, print the actual placement.**
`accelerate` decides on the devices it can see, not the devices you meant, and
on a shared or desktop box that includes the one you reserved for something
else. The failure is not an error: the model loads, generates, and returns
garbage, because layers landed across a boundary they should not have crossed
([trap 39](../traps/runtime/39-device-map-auto-offloads-and-returns-garbage.md)).
Read `model.hf_device_map` and compare it against what you intended, and set
`CUDA_VISIBLE_DEVICES` rather than trusting `auto` to respect your intent.

**2. Before you believe any delta, measure your own agreement floor.** Load
the same weights twice, score the same items, and see how far apart the two
runs land. On this stack, at bf16, on identical weights and a fixed seed, they
do not land in the same place
([trap 35](../traps/evaluation/35-identical-weights-do-not-score-identically.md),
**Core**). Until you have that number, every small delta you publish is
unfounded, and the number is a property of your setup rather than something
you can borrow from this page.

**3. Check that your token cap is not doing the work.** `max_new_tokens` is
not a neutral constant across arms: a reasoning arm and a non-reasoning arm
spend it differently, so a single cap handicaps one of them and the handicap
reads as a capability difference
([trap 36](../traps/evaluation/36-token-cap-is-an-arm-level-handicap.md)).
Split your results on whether generation stopped because it finished or
because it ran out, before aggregating anything.

## The entries that name this stack

| Entry | Status | What it does to you |
|---|---|---|
| [39, `device_map="auto"` grabs a device you excluded](../traps/runtime/39-device-map-auto-offloads-and-returns-garbage.md) | reported by others | The load succeeds, generation runs, and the output is garbage. No error at any point |
| [35, identical weights do not score identically](../traps/evaluation/35-identical-weights-do-not-score-identically.md) (**Core**) | reproduced here | Without your own floor, every small delta you publish is unfounded |
| [34, winning against a baseline you degraded yourself](../traps/evaluation/34-baseline-you-degraded-yourself.md) | reported by others | Any A/B whose reference arm is a non-default configuration is exposed |
| [36, the token cap is a per-arm handicap](../traps/evaluation/36-token-cap-is-an-arm-level-handicap.md) | reported by others | One cap across two arms that spend tokens differently is a handicap, not a control |
| [33, raising a MoE's inference top-k costs accuracy](../traps/routing/33-moe-inference-topk-expansion-tax.md) | reported by others | The one entry on this page with a first-party half, and that half is NVFP4 on vLLM rather than bf16 here |
| [41, static batching bought power, not throughput](../traps/runtime/41-static-batching-buys-power-not-throughput.md) | reported by others | A hand-rolled batching loop over variable-length outputs pays for the longest sequence in every batch |
| [50, hidden-state dump conventions differ](../traps/evaluation/50-hidden-state-dump-convention.md) | contributor-measured, conditions as reported | A `trust_remote_code` modeling file sets `output_hidden_states` semantics, manufacturing a "final-layer norm explosion" that is a convention difference |

## Two honest caveats on the counting

- Trap **41** counts for this stack and for vLLM, and the vLLM mention is the
  **contrast arm**: it is the thing that did not have the problem. The count
  rule cannot tell a stack that was bitten from a stack named as the fix, and
  this is one of the cases where it matters.
- Traps **34**, **35** and **36** are stack-independent classes that happen to
  have been measured here. They are on this page because this is where the
  evidence came from, not because the defect lives in `generate()`. You can
  hit all three on vLLM.

## What the doctor can do here

Nothing directly. The [doctor](../doctor/) is a request-shaped tool that talks
to an OpenAI-compatible endpoint, and this stack is a library rather than a
server. If you serve these weights behind an OpenAI-compatible wrapper, the
doctor sees the wrapper, and the placement and batching traps above are
invisible to it either way.
[`checks/preflight_template.py`](../checks/preflight_template.py) accepts
`--template-file`, so the template half of the registry does port here.

## Where a report would help most

This stack has **no first-party coverage on the stack itself**, and it is
where a large share of eval work happens. The single most useful thing one
person could contribute is a **measured agreement floor of their own**: two
loads of identical weights, same seed, same items, and the spread between
them, on hardware that is not @Hikari_07_jp's and on `generate()` rather than
on a server. Trap 35's originating measurement is one person's, on two of
their hosts, and it is load-bearing for every delta anyone publishes. Our
reproduction is on a different build class, so it generalises the class
without adding a second bf16 `generate()` number. A third, independent one
would either harden it or bound it.

Reports go in the [easy door](../../../issues/new?template=report-a-trap.yml);
scrub your logs first.
