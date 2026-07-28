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

   <!-- status-vocabulary: full-set -->
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

## Merge contributor PRs, do not apply them

**Merge through GitHub. Do not `git checkout <branch> -- <paths>` onto `main`.**

Applying a contributor's files to `main` produces a result that looks identical
in the tree and is not identical to them. Their branch and `main` have then
independently modified the same paths, so their PR shows conflicts on every file
they wrote plus whatever else moved, and their check run is their branch against
a `main` that has moved past it. They see a red X on their own work while the
maintainer comments say it is merged.

It also throws away the only attribution git records. Entry credit lines,
HALL_OF_FAME and the CHANGELOG survive, because those name the person. The merge
does not, and it cannot be added afterwards.

This happened to traps 99 to 104 and the PR had to be closed unmerged with an
explanation. The remainder of that batch, trap 98, is deliberately being held so
it can land as its own PR and carry his merge.

**Checklist when a contributor PR needs maintainer edits before it can land:**

1. Push the edits to their branch if they have granted maintainer access, or ask
   for them, or land the batch minus the contested entries and take the rest as
   a follow-up PR. All three preserve the merge.
2. If none of those is possible and it must be applied directly, say so **in the
   PR at the time**, name the attribution cost, and offer the remainder as its
   own PR. The [contributor-facing statement](CONTRIBUTING.md#how-your-pr-gets-landed-and-what-that-does-to-your-attribution)
   is what we have committed to them.
3. Never leave a PR showing conflicts against content `main` already has.
   Resolving it reconciles their branch against work that is already in, and it
   can quietly reintroduce anything the maintainer deliberately held back. Close
   it with an explanation instead.

**One platform note, because it is easy to promise and impossible to deliver.**
`state_reason: completed` cannot be set on a pull request. It is an issues-only
field: a PR is merged or it is closed, and a close carries no completed or
not-planned distinction. If the intent is to say the work was completed rather
than abandoned, that has to be in the closing comment, because the API will not
carry it.

## The site bot races you, and index.html is generated

Pushing to this repo triggers the build workflow in
`Blackwellboy/Blackwellboy.github.io`, which regenerates `index.html` from this
tree and commits it. If you are editing that repo's sources at the same time,
your push is rejected and you are left holding a conflict in a **generated**
file.

**Resolution, and it is not the obvious one.** Do not merge `index.html`. Take
your `build.py` and `index.template.html`, then **regenerate** `index.html` and
stage the result:

```bash
git checkout <your-commit> -- build.py index.template.html
python3 build.py --registry ../model-serving-minefield
git add build.py index.template.html index.html
git rebase --continue
```

Hand-merging a generated file produces something neither generator would emit,
and the next scheduled build silently replaces it, so any hand-resolution you
did is lost without a signal.

**Why not just serialise them.** The bot fires on push and has no way to know a
human is mid-edit, and adding a lock the bot must respect means the bot can
block on a stale lock and the page stops updating. A page that quietly stops
regenerating is the failure mode this repo has already had twice. A rejected
push is loud and costs one rebase; a wedged generator is silent and costs days.

**What to do before a session that touches both.** Take the claim on the site
clone the same way as the registry, which stops two *humans* colliding even
though it cannot stop the bot:

```bash
repo-claim claim ~/publish/model-serving-minefield --session <name>
repo-claim claim <site-clone> --session <name>
```

Land registry changes first, let the bot rebuild, then edit the site. The race
only bites when the order is reversed.

## Numbering in this merge

**Numbers in the 43-and-up range are provisional until the contributors whose
work they carry have had a chance to object.** Stating that here rather than
only in a PR thread, because a thread scrolls and this file does not.

On 2026-07-28 five independently staged sets all wanted numbers from 43 upward:
one large external contribution and four first-party coverage batches. There is
no ordering of five competing sets that leaves every set's provisional numbers
intact, so the numbers were assigned **at merge, in merge order, gapless**,
which is what [CONTRIBUTING](CONTRIBUTING.md#external-pr-policy) already
promises external contributors ("if entries land underneath you while your PR is
open, **we** rebase the numbers at merge, not you").

What that meant in practice:

- The external block landed **first and at its own base**, so its lowest number
  was preserved. That was deliberate: it is the only set whose numbering was
  already visible to somebody outside this repo, so it is the only set where
  renumbering would cost a third party rather than us. **Preserving the base is
  not the same as nothing moving**, and this file said the stronger, false
  thing first: one entry folded and one was held, so everything above the base
  slid down one place and the sweep rewrote the internal cross-references to
  match. The full map is below.
- Every first-party set was renumbered around it, not the other way round.
- One title collided. Both entries were real and distinct, so both landed and
  **ours was the one renamed**, because the phrase came from the contributor's
  corpus in the first place. The two cross-link.

### The PR-to-main number map

The base was preserved, so 43 is still 43. But folding one entry and holding
another removed two numbers from the middle of the range, so **everything above
43 slid down by one place** against the numbers published in the PR. Twelve
entries moved. Saying "the base was preserved" and saying "nothing moved" are
different claims, and the first one is the true one.

This map is here so an external bookmark can be resolved without reading a PR
thread. Slugs did not change, so a link to a filename still resolves; a bare
number from the PR does not.

| PR #1 | now on main | slug |
|---|---|---|
| 43 | **43** | `tool-args-string-not-mapping` |
| 44 | *folded into 12 and 22* | `retry-on-truncation-residual-tail` |
| 45 | **44** | `fp4-dequant-scale-swizzle-layout` |
| 46 | **45** | `fa-all-quants-cpu-fallback` |
| 47 | **46** | `stale-build-missing-arch-kernel` |
| 48 | **47** | `prefix-caching-autodisabled-hybrid` |
| 49 | **48** | `dual-stack-mdns-latency-tax` |
| 50 | **49** | `prompt-not-tokenized-to-target` |
| 51 | **50** | `hidden-state-dump-convention` |
| 52 | **51** | `single-backend-nan-fused-path` |
| 53 | **52** | `speed-measured-on-a-broken-config` |
| 54 | **53** | `config-edit-never-took-effect` |
| 55 | **54** | `run-order-and-warm-cache-artifacts` |
| 56 | *held* | `kv-quant-unread-without-chunked-prefill` |
| 57 | **55** | `supported-context-is-not-trained-context` |

**The PR's 56 is not the current trap 56.** It is held; the current 56 is one of
ours. That is the collision a bare bookmarked number would hit.

**This was stated wrongly first.** The merge note and this file both originally
said no entry of his moved and his cross-references were unchanged. Neither was
true: the sweep rewrote those cross-references, which is why they still resolve.
The correction is
[on the PR thread](https://github.com/Blackwellboy/model-serving-minefield/pull/1)
as its own comment rather than as an edit, because the wrong version had already
been read.

If you contributed to this range and want any of it renumbered or renamed,
including a title, say so and we will run the sweep. That is not a courtesy
offer with a cost attached to taking it up: the sweep is parameterised by the
base and it is verified against dangling links in filenames, headers, in-body
references and index rows, so moving a block is cheap and moving it back is
equally cheap.

## Cadence

Reports get a first maintainer response within a few days. Entries land as
they are verified. The [CHANGELOG.md](CHANGELOG.md) is the liveness record.
