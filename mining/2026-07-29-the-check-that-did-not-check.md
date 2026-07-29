# The check that did not check: four cases, one habit

**Date:** 2026-07-29
**Kind:** methodology, ours. Not serving defects.

## Why this is here and not in `traps/`

`traps/` documents failures in serving stacks that cost an operator time. Every
case below is a failure in **our own verification**, and the victim is a reader
who trusted a green result. They have no lane, no config and no reproduction on
hardware.

They are one document rather than four because **the pattern is the finding**.
Each case on its own reads as a slip. Together they are a habit: a check was
written, it reported success, and nobody asked what it had actually inspected.

## Case 1: fixing a defect class in one file does not inoculate the next

`COUNT-WORD` was written to catch a registry total spelled as a word. Its first
version scanned line by line, and the instance it was built for is wrapped
across a line break in README, so it could not see the exact string it existed
for. That was found and fixed the same morning: scan the file as one string,
recover the line number from the match offset.

Hours later `verify_surfaces.py` was written fresh, with patterns using a
literal space, against the same wrapped source. It matched the two single-line
occurrences of the registry total and silently skipped the wrapped one.

**It reported CLEAN over a mutation that had genuinely applied.** The only
reason it was caught is that the harness printed `mutation applied` while the
checker printed `CLEAN`, and the two lines disagreed on screen.

**The check.** When a mutation test passes, verify the mutation actually landed
before believing the result. A passing test and an applied mutation are two
separate facts and the harness must print both.

## Case 2: a mutation test can pass for the wrong reason

The check-contract manifest was meant to assert that discovery finds what the
registry expects, in both directions. The first missing-direction test removed
the only check in the tree.

That tripped the **pre-existing empty-set guard**, not the new manifest
assertion. The test went red, the guard looked proven, and it was not: the same
red would have appeared with the manifest code deleted entirely.

Proving it honestly needed two checks, so the set could be non-empty and still
wrong. Only then did the assertion have to do any work.

**The check.** A guard proven by a test that would have passed without it is
unproven. Ask what else could produce this red, and if an older guard could,
the test is measuring the older guard.

## Case 3: a comment is not a check

`test_reference_mutations.py` builds its fixture by copying an explicit list of
paths. Adding a README link to `llms.txt`, which was not on that list, made the
link dangle **inside the copy** and four tests went red against a tree that was
green.

The comment directly above that list already described this exact failure
happening once before, with `upstream/`, and explained why a partial copy is a
mutation nobody intended. The comment was correct, prominent, and did nothing.

**The check.** If a comment explains why something must not happen, that is a
specification with no enforcement. Either derive the thing the comment is
guarding, or make its omission fail loudly. Prose next to code is documentation
of a hazard, not a control on it.

## Case 4: a status field is not a capability probe

`wsl --list --verbose` reported `Running` continuously while the distro went
from working, to roughly one exec in three succeeding, to eight of eight
hanging. The status never changed. Host memory was not exhausted, and the
service answered every time it was asked.

Two things made the true state visible, and neither is a status read. A **timed
exec** distinguished hung from slow. And a **mixed workload** distinguished the
intermediate state: `/bin/true` returning while `/bin/echo` failed is the signal
that something is degrading, and a single uniform probe reads either result as
the whole truth.

A single probe was taken at one point on a declining curve and reported as a
static state. The reading was wrong in a way that mattered: at one-in-three,
careful single-shot reads are possible and multi-step mutation is not, which is
a different operational conclusion from "wedged".

**The check.** Gate on a timed exec of the real workload, not on a status field,
and sample enough to see intermittency. Anything gating on distro status would
have reported that machine healthy for the entire degradation.

## Where a serving-side version would go

If a `/health` endpoint ever returns 200 while generation is wedged, that is a
serving defect and belongs in `traps/`, not here. It is **not** claimed on the
strength of a WSL incident: generalising one infrastructure observation into a
serving claim is exactly the over-reach the status vocabulary exists to
prevent. The note is here so that if it is observed, it is recognised.