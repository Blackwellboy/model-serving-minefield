# Trap 22: a family card is not a model card, the thinking budget floor differs by size

**Found by Blackwellboy.**

**Status: reproduced here** for the published 40-sample map on Qwen 3.6
35B-A3B
([qwen-ceiling](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/qwen-ceiling),
raw published, and the multi-sample check below re-derives the phenomenon on
your own lane), and **measured here, raw not published** for the three-lane
production replication that carries the per-size claim (n=2 to 3 per cell,
rows in a private return).

**The per-size claim rests on the multi-sample replication below, not on the
single-sample pilot.** An earlier version of this entry led with a
one-sample-per-cell table and called the whole thing reproduced here. One
sample per cell cannot establish a floor, because the floor turned out not to
be a threshold at all.

**Symptom.** You set the max_tokens ceiling that worked fine on one member
of a model family, run its sibling, and hard tasks come back as HTTP 200
with empty content (trap 12's signature). The family-level advice ("8K is
plenty for thinking models") was a model-level fact.

**Mechanism.** Thinking-token demand on the same task varies by multiples
between sizes of one family, so the budget that converts empties on one size
still starves another.

### Primary evidence: three production lanes, n=2 to 3 per cell

Byte-identical six-requirement coding task, thinking explicitly on,
llama.cpp, production lanes, nonce-prefixed samples (2026-07-27 ceiling-audit
session). Cells are **conversions over samples**:

| Lane / model | 4096 | 8192 | 12288 | 16384 |
|---|---|---|---|---|
| 27B Q4_K_M (production controller) | 0/3 | 0/3 | 1/3 | **2/3** |
| 9B Q4_K_M (verifier lane) | 0/2 | 1/2 | 2/2 | 2/2 |
| 35B-A3B Q3 heretic (critic lane, 3090) | 0/2 | 1/2 | 2/2 | 1/2 |

Two things this establishes that the pilot could not:

1. **The floor is a DISTRIBUTION, not a number.** The 27B produced 26K to
   61K chars of reasoning on the identical prompt, so 16384 still fails 1 in
   3. There is no ceiling you can set and call the problem solved; there is
   only a rate you can measure and decide to accept. Any single-sample probe,
   including [the doctor's](../../doctor/), can land on either side of that
   and tell you nothing.
2. **Every capped tail was honest truncation, not a degeneration loop** (tail
   unique-line ratio 0.78 to 1.0, zlib 0.30 to 0.44), so budget really was
   the binding constraint and not a symptom of the model looping.

The per-size spread is the point and it survives here: at 8192 the 9B and the
35B-A3B convert half their samples while the 27B converts none.

Raw: `ceiling_audit_20260727.jsonl` (28 rows), **private return, not
published**, which is why this half of the entry is labelled measured-here
rather than reproduced-here. The check below re-derives it on your lane.

**Control (the operational half).** The same task with NO thinking kwarg
completes on all three lanes in 1.5K to 5K completion tokens with zero
reasoning chars. The budget floor only exists when thinking is on, which is
exactly why
[trap 29](../reasoning/29-server-reasoning-off-is-not-an-off-switch.md)
matters: one client kwarg that re-enables thinking on a reasoning-off lane
walks the request straight onto this floor.

### Corroborating: a published 40-sample map

The published 40-sample map on Qwen 3.6 35B-A3B (vLLM, different task,
different stack) converts at 8192
([qwen-ceiling](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/qwen-ceiling)).
This is the only cell in the entry whose raw a reader can open.

### Pilot, n=1 per cell: how this was first noticed

Kept because it is where the entry came from, and marked because a single
sample per cell cannot support a floor. **Do not quote these as measured
floors.** The multi-sample table above supersedes them and disagrees with
them: the pilot reads 8192 as the 9B's converting budget, where n=2 has it
converting only 1 in 2.

| max_tokens | Qwen3.5-9B Q4_K_M | Qwen3.6-27B Q4_K_M |
|---|---|---|
| 512 | empty content at cap | empty content at cap |
| 4096 | empty content at cap (~15K chars reasoning) | empty content at cap |
| 8192 | converts (1 sample) | empty content at cap (~30K chars reasoning) |
| 16384 | not run | converts (1 sample, ~42K chars reasoning) |

The 27B's 16K-conversion tail here is non-degenerate (unique-line ratio 0.81,
zlib ratio 0.34), consistent with the multi-sample finding above.

**Stacks and builds bitten.** Primary: three llama.cpp production lanes
(27B Q4_K_M controller, 9B Q4_K_M verifier, 35B-A3B Q3 heretic on a 3090),
n=2 to 3 per cell across four budgets. Corroborating: vLLM/GB10
(Qwen3.6-35B-A3B NVFP4), 40-sample published map. Pilot only: llama.cpp
b9066 (Qwen3.5-9B Q4_K_M) and b9193 (Qwen3.6-27B Q4_K_M), one sample per
cell. Task difficulty obviously shifts the absolute numbers; the per-size
spread is the point.

**The check.** Before trusting any per-family budget guidance: run your
hardest routine task at your production ceiling on THE model you deploy,
thinking on, and check for empty content at cap.

**Run it at least three times per budget.** One request does not answer this,
and an earlier version of this entry said it did. A single pass is a coin
flip on a distribution: the 27B above converts 2 of 3 at 16384, so one lucky
request certifies a ceiling that fails a third of your traffic. Sweep at
least two budgets and take the conversion RATE, not a yes or no. If you want
the shape of the tail as well, record the unique-line and zlib ratios of the
capped reasoning so you can tell honest truncation from a loop
([trap 16](16-finish-reason-is-not-a-failure-signal.md)).

**The fix.** Set ceilings per model, not per family, and re-measure on
every size or variant swap (trap 14's discipline applied to budgets).
When a cap-hit appears, apply trap 16's bucketing before concluding
anything.

**Found.** 2026-07-27, standardized probe sweep plus follow-up arms.

**Attribution.** Blackwellboy. Probe and follow-up JSONs in the sweep
results (`probe_*`, `hfollow_*`, `hdegen_*`).

## A note on how this entry changed

It first landed leading with the n=1 pilot table and a status of "reproduced
here", with the multi-sample production replication appended underneath as a
follow-up. That inverted the evidence: the weakest table set the headline and
the strongest one read as an addendum, and the entry's own check told readers
one request would settle a question its own data showed one request cannot.
The tables are unchanged; which one leads, and what the status claims, are.

## Added 2026-07-28: a third family, and why its floor is not transferable either

A fully crossed budget sweep on the NVIDIA Nemotron 3 family found a hard-task
floor between 64 and 128 tokens on one member while a harder probe on the same
lane still returned empty at 512. The full table and its conditions are in
[trap 12](12-empty-content-at-token-ceiling.md). It is recorded there rather
than here because it is a within-member task effect, but it belongs next to
this entry for one reason: it is a second demonstration that a floor measured
on one task, one member and one difficulty is not a number to copy anywhere.

*Status of this addendum: measured here, raw not published.*
