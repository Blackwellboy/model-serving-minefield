# Maintaining the registry

How a report becomes an entry, and the conventions that keep credit and
honesty straight. Written for maintainers, readable by anyone who wants to
know what happens to their issue.

## The two doors

- **Easy door:** the ["I hit a trap" issue form](../../issues/new?template=report-a-trap.yml).
  Four plain questions. No evidence bar is applied to the report itself; the
  bar applies to the entry a maintainer later writes from it.
- **Full door:** a PR with a complete entry per
  [CONTRIBUTING.md](CONTRIBUTING.md).

Both doors end in the same place: a credited entry. The easy door just moves
the writing and verification work to a maintainer.

## Promoting an issue to an entry

1. **Read the report and check for a match.** If the symptom matches an
   existing entry, reply with the link. If the reporter's stack is new for
   that entry, add it to "Stacks and builds bitten" and credit them in the
   Attribution section. Close with thanks; that still counts as a
   contribution.
2. **Verify what can be verified.** If the trap is reproducible on hardware
   we have, run the check or a minimal repro. If it is not reproducible here
   (different hardware, proprietary stack), verify internal consistency:
   does the mechanism explain the symptom, does the fix follow from the
   mechanism, is there a runnable check.
3. **Write the entry** in the CONTRIBUTING format, in the reporter's terms
   where possible; their phrasing of the symptom is usually the phrasing the
   next victim will search for.
4. **Mark status honestly.** The vocabulary is a closed set and it is defined
   once, in
   [CONTRIBUTING.md](CONTRIBUTING.md#status-vocabulary). Do not restate it
   here and do not paraphrase it in an entry: this file used to say
   "reproduced here: we ran it and can link **or produce** the raw", which
   let a promise stand in for evidence. It cannot. A stranger reading the
   entry is the only person the label exists for, and they cannot act on an
   offer to send them files.

   The labels are **reproduced here**, **contributor-measured, conditions as
   reported**, **reported by others**, **measured here, raw not published**,
   and **under test**. Each carries an evidence pointer. Reported,
   contributor-measured and unpublished-raw entries are labelled, never
   rejected.
5. **Credit the reporter.** Their handle goes in the **Found by** line at
   the top of the entry, in the Attribution section, and in
   [HALL_OF_FAME.md](HALL_OF_FAME.md). Link the originating issue from the
   entry's Attribution section. Contributors are always named unless they
   ask otherwise; use a generic label for anything not publicly
   attributable.
6. **Wire it in.** Add the symptom row in `README.md`, the model row in
   [models/README.md](models/README.md) if a model family is named, and a
   line in [CHANGELOG.md](CHANGELOG.md).
7. **Close the loop.** Comment on the issue with the entry link before
   closing it.

## Status transitions

- **under test** resolves to **reproduced here** or drops to **reported by
  others** or **contributor-measured** with a dated note on what the
  replication attempt found. A failed replication is recorded in the entry,
  not silently deleted; "did not reproduce on stack X" is information.
- **measured here, raw not published** converts to **reproduced here** the
  day either the raw is published at a URL, the raw ships in-repo, or someone
  writes a check a stranger can run to re-derive the finding. That last one
  is usually the cheapest of the three and it is the one to reach for first.
- **contributor-measured** gains the second half of a compound status when we
  reproduce it here. The contributor keeps the **Found by** line either way.
- Corrections to any entry or attribution are fixed fast; open an issue.

## Shipping raw data in the repo

This is a text-first repo. The default is that an entry **links** its raw, or
ships a check a stranger can run, and the raw itself lives outside the tree.
Keeping it that way is what makes the registry cheap to clone and quick to
read. Note that "we can produce it on request" is not one of the options: see
[the status vocabulary](CONTRIBUTING.md#what-reproduced-here-requires).

There is one exception, and it is deliberate rather than an oversight:

**When an entry is a calibration constant that other entries cite, its raw data
ships in-repo, and a runnable verifier ships with it.** A number that other
conclusions are measured against has to be checkable without asking anyone for
files. If a reader cannot re-derive it from the tree, every entry that leans on
it inherits an unverifiable dependency.

Conditions, all three required:

1. Other entries cite the number as a threshold, floor or baseline. A one-off
   measurement, however good, does not qualify.
2. A verifier ships beside the data, runs with no arguments, resolves its own
   paths, and prints a pass or fail per published figure. Data without a
   verifier is just weight.
3. The verifier is written independently of whatever produced the numbers, so
   that a bug in the original does not reproduce itself in the check.

The worked example is
[the agreement floor](mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md),
whose `verify_numbers.py` re-derives every published figure from the shipped
answer sheets. Writing that verifier caught two defects in the draft before
publication, which is the argument for the rule in one sentence.

If an entry does not meet all three conditions, link the data instead. If a
calibration entry's data would be large enough to change the character of the
repo, prefer a release asset and say in the entry where it lives.

## Cadence

Reports get a first maintainer response within a few days. Entries land as
they are verified. The [CHANGELOG.md](CHANGELOG.md) is the liveness record.
