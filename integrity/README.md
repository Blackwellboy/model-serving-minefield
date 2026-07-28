# integrity/

The automated consistency layer for this registry and the lab repo it draws
from.

## Why it exists

Three independent audits found the same class of problem, three times, in
three places: a correction lands on one surface and another surface keeps
teaching the old thing; a status word means different things in different
entries; a trap count goes stale in a launch document. Every instance was
caught by a human reading carefully. That does not scale, and by the time it
was noticed each one had already cost a real error.

Every check here exists because a specific failure happened. None of them are
speculative, and each one is exercised by a mutation test that reintroduces
the exact failure it was built for.

## Run everything

One command, from either repo:

```bash
python3 integrity/run_checks.py --peer ../laguna-s21-lab
```

## Run one check

```bash
python3 integrity/registry_integrity.py
```

```bash
python3 integrity/claim_propagation.py --repo minefield=. --repo laguna=../laguna-s21-lab
```

```bash
python3 integrity/do_not_cite.py --base origin/main
```

```bash
python3 -m unittest discover -s integrity/tests -t integrity/tests
```

From the lab repo, pointing at the checkers in this one:

```bash
python3 ../model-serving-minefield/integrity/claim_propagation.py --ledger ../model-serving-minefield/integrity/claims.json --repo laguna=. --repo minefield=../model-serving-minefield
```

## Install the hook

```bash
ln -sf ../../integrity/hooks/pre-push .git/hooks/pre-push
```

## What each check does

**registry_integrity.py.** For every numbered entry: a row in the README
symptom table, a status in both places drawn from the closed vocabulary, a
finder named at the top, a HALL_OF_FAME credit if the finder is not us, a
listing in the per-model or per-stack index, a CHANGELOG announcement, and
every relative link resolving on disk. Repo-wide: the redirect stubs still
point somewhere real, and every stated registry total agrees with the tree.

Counting rule: an entry is `traps/<category>/NN-*.md`. The seven flat
`traps/NN-*.md` files are redirect stubs from the category reorganisation and
are never counted. `CHANGELOG.md` is exempt from the count check because it is
an append-only record of what was true on a date.

The status vocabulary is a closed set defined in
[CONTRIBUTING.md](../CONTRIBUTING.md#status-vocabulary). It is mirrored in
`registry_config.json`, and the checker asserts every mirrored label still
appears in CONTRIBUTING.md, so this directory cannot end up enforcing a
vocabulary nobody documented.

**claim_propagation.py.** The one that would have caught the worst failures.
`claims.json` maps every retracted, corrected or scope-limited claim to every
surface that carries it, across both public repos, our posted upstream
comments, and third-party guides that cite us. The checker greps for the
distinctive phrasings recorded with each retraction and reports three
verdicts: FLAGGED (superseded wording with no correction attached, the
failure), CONTEXT (superseded wording with its correction nearby, which is the
visible-corrections convention working), EXEMPT (a verbatim archive or the
retraction record itself). Remote surfaces are printed as MANUAL with their
URLs every run.

**The rule this encodes: a retraction is not complete until its search terms
are recorded.** The ledger validator refuses any retraction with no
`search_phrasings`, no note on each phrasing, no `superseded_by`, no
`authority`, and no `correction_anchors`. Recording the phrasing is what makes
a retraction enforceable on surfaces that do not exist yet.

Two design points learned during bring-up, both kept as tests:

- A correction only counts if it is about the same claim. Without
  `correction_anchors`, an unrelated correction thirty lines below an
  uncorrected paragraph vouched for it.
- Anchors must be distinctive. `qwen` in a Qwen-heavy repo is not an anchor.

**do_not_cite.py.** The do-not-cite list, made mechanical. Runs on ADDED text
by default (diff plus untracked files, because a new writeup is entirely added
text and `git diff` does not show it). Tuned for low false positives: items
that cannot be matched without firing on ordinary prose are recorded in the
`manual_only` block and printed every run rather than dropped, so the list
stays complete while the enforced part stays quiet enough to be believed.

**The sanitizer whole-tree scan.** Runs in the hook, never in CI. Its pattern
file is the list of internal hostnames, usernames, path fragments and
codenames it scans for, so publishing it to a public runner would publish the
thing it protects. `run_checks.py` prints SKIPPED, in those words, when the
private kit is absent, rather than a pass it did not earn. Point it at the kit
with `MINEFIELD_SANITIZER_KIT`.

## Running in CI

Both public repos run this layer on push to main, on pull requests, and on
demand. Two rules were learned the hard way on the first red run and are worth
stating, because both are easy to reintroduce:

**A nested checkout is a different repository.** The peer repo must be checked
out OUTSIDE the workspace. When it was placed at `.peer/` inside it, every peer
file was scanned twice, once under its own repo name and once under this repo's
name, where its exemptions did not apply. A correctly exempt line was reported
as a failure and the build went red on a non-finding. The checkers now prune
any directory containing a `.git` entry and print what they pruned, so the tool
is right regardless of layout, and the workflows put the peer in `RUNNER_TEMP`
so the situation does not arise. The sibling workflow with the same layout
passed, which was worse: it was green for the wrong reason.

**Every check runs, and the badge says which one failed.** Steps carry
`if: always()` and a final verdict step prints PASS or FAIL per check. Without
that, one failure skips the rest and the badge reports one broken thing while
saying nothing about the others.

Pass `--github` to any of the three checkers to emit GitHub Actions
annotations. Findings then name the file, the line, what matched and the
correct form of the claim, instead of `Process completed with exit code 1`.

## Proving the checks have teeth

`integrity/tests/test_mutations.py` reintroduces each historical failure on a
throwaway copy of the tree and asserts the check fails with a message that
names the file and the missing thing. Every mutation carries a negative
control, because a checker that flags everything passes a mutation test and is
useless.

Run it after touching anything in this directory. A green run of the checks
themselves is not evidence; a green run of the mutations is.

## Two things that made this hook a no-op, both found on 2026-07-28

The pre-push hook is the only place the sanitizer runs, because its pattern file
cannot be published to a CI runner. That makes a silently inert hook the worst
failure this layer can have, and it had two, stacked, on the first push that
tried to use it.

**1. It could not find itself.** The install instruction is `ln -sf` into
`.git/hooks/`. `BASH_SOURCE` is then the symlink's own path, so `dirname` gave
`.git/hooks`, `INTEGRITY` became `.git/`, and every push was refused with
`can't open .git/run_checks.py`. That is fail-closed and therefore not
dangerous, but the documented install produced a hook that could never pass.
Fixed by resolving the symlink with `readlink -f` before the dirname, plus an
explicit existence check so the next path bug says what is wrong instead of
surfacing as a Python file-not-found.

**2. Git ignored it, and said so in a hint.** The symlink target was not
executable, so git printed

```
hint: The '.git/hooks/pre-push' hook was ignored because it's not set as executable.
```

and pushed anyway. This is the dangerous one, and it is the same shape as
everything else this repo audits: **a check that does not run looks exactly
like a check that passed**, and the only signal was a hint above the push
output that a human skims past. The file is now committed with the executable
bit set, so a fresh clone symlinks a hook that git will actually invoke.

**If you are installing this hook, verify it fires rather than assuming it.**
Run it directly once and confirm you get the SUMMARY block:

```bash
ln -sf ../../integrity/hooks/pre-push .git/hooks/pre-push
.git/hooks/pre-push origin <remote-url> </dev/null
```

A hook you have not seen produce output is a hook you are assuming.

## The contradiction gate, and the absence gate that was abandoned first

`contradiction_gate.py` fails the build when an entry claims **reproduced here**
while the entry, or a file it links to one hop away, asserts that the result is
not checkable. That is the trap-33 defect exactly: the entry claimed the label
while its data README said "you cannot check our rows".

**It gates on the contradiction, not on absence, and that was the second
design.** The first one asked "does an entry claiming reproduced here NAME its
evidence". It was attempted twice and abandoned, and the reasoning is kept here
because the failure is not obvious and is worth not repeating.

- **Matching phrasing** ("publicly obtainable", "without asking us") is a proxy
  for evidence rather than evidence. An entry that says the words while naming
  nothing passes; an honest entry that names a file in neutral prose fails.
- **Matching shape** (a URL, an in-repo path, a runnable command) is better and
  still wrong. Measured across all 81 entries it failed **36 of the 61** that
  claim the label, and spot-checking found them mostly honest: trap 56's check
  is a four-case procedure against a public checkpoint, trap 72's is a
  one-request probe this repo's own doctor runs. Both are legitimate under
  CONTRIBUTING form 3, and both are stated in **prose**.
- Loosened far enough to accept prose, the shape became nearly unfailable: one
  version "passed" trap 12 on a see-also link to a sibling entry, which is
  defect shape 1 from CONTRIBUTING, a sentinel present in its own input.

The obstacle is structural. Form 3 permits a runnable procedure described in
prose, and prose is not mechanically distinguishable from absence, so an
absence-gate must either fire on honest entries or be unfailable.

The contradiction gate has neither problem, because it never asks whether
evidence exists. It fires on **zero of the 81** entries as they stand, which is
the correct result and also exactly what a broken gate looks like, so its teeth
are asserted by mutation rather than assumed:
`integrity/tests/test_contradiction_gate.py`, 11 cases, both directions,
including the honest-prose-procedure case that killed the absence gate and the
one-hop case that is the whole point.

Three exemptions, each measured rather than assumed. Following into them fired
on 12 entries, every one a false positive:

1. **Policy documents.** Every entry links CONTRIBUTING, which discusses
   non-checkability generically.
2. **Sibling entries.** Another entry's limits are not this entry's
   contradiction, and entries cross-link constantly.
3. **Labelled sub-sections.** A folded contributor addendum whose raw is private
   says so and is labelled contributor-measured; that is the addendum's limit,
   not the host entry's.

A correctly stated compound status is also exempt: "reproduced here for the
arithmetic and measured here, raw not published for the curve" is precision, and
a gate that punished it would push entries toward vagueness.

## Known and accepted residuals

Written down because an unstated limitation reads as a guarantee, which is the
failure this whole layer exists to prevent.

**The pre-push hook is a content trust model, not a guarantee.** It can be
replaced by an inert executable that exits 0 having run nothing, and git will
invoke it happily. That is not a regression of the executable-bit fix: an
authentic hook fails closed, and the fix ensures an authentic hook actually
runs. What neither can do is prove the file on disk is the one in this repo.
Anyone treating a green pre-push as evidence that the sanitizer ran should
verify the hook resolves to `integrity/hooks/pre-push` and check the SUMMARY
block appeared. **A hook you have not seen produce output is a hook you are
assuming**, and that holds whether the cause is a missing bit or a substituted
file.

**CHANGELOG.md is exempt from the COUNT check, by design.** It is an
append-only record of what was true on a date, so a 2026-07-28 line reading
"corrected to 17 of 42" must keep saying 42 after the tree grows or the log
stops being a log. The consequence, accepted: **a wrong count introduced into
the CHANGELOG will never be caught mechanically.** Every other surface is
checked, including orphan forms like "not implemented N", which are asserted as
total minus implemented after one such number survived two registry expansions.
The CHANGELOG is the one place a reader must not infer current coverage from a
number, and its entries are dated so that reading is available to them.

**Documents outside this repository are structurally out of reach, and stale
registry facts there will not be caught.** This is the third residual and it is
the one with the widest blast radius, so it is written down rather than left to
the assumption that CI covers it.

The COUNT check asserts every declared total against the tree it can see. That
tree is this repository. Other surfaces describe this repository's state and are
not in it:

- a private control-plane continuity document that cold-start agents read as
  authoritative,
- a personal site that quotes an entry count in prose,
- session returns and handoff notes that quote a tip SHA and a count.

On 2026-07-28 the continuity document said **42** and the site said **32** while
the live tree held **90**. Both were found by hand, one by an archive
excavation and one by a sweep, and neither could have been found by anything in
this directory.

**Can the layer reach them? No, and not for a reason worth engineering around.**
Three options were considered and all three are worse than the residual:

1. **Scan sibling paths from CI.** The public runner has no access to a private
   control-plane tree, and giving it access would put that tree on a public
   runner, which is the thing the sanitizer's pattern file already cannot do.
2. **Have the other documents pull the count at render time.** They are hand-
   written prose in repositories with no build step. Adding one to make a
   sentence self-updating is a large change to buy a small guarantee.
3. **A cross-repo checker run locally.** This is the only workable one, and it
   still cannot be a gate, because nothing forces it to run before somebody
   reads the stale document. It would be a periodic sweep, not a check.

**So the honest statement is: any count outside this repository is a snapshot,
and the only thing that makes it trustworthy is the tip SHA printed beside it.**
That is the convention to enforce socially rather than mechanically: never write
a bare count, always write the count and the tip it was counted at, so a reader
can tell in one command whether it still holds. The count in this repository is
checked; every count elsewhere is a claim about a moment.

For scale, because it argues the point better than the rule does: this
registry's entry count went **42 to 81 to 90 within a single day**. A document
that quotes it without a tip is wrong within hours, and no amount of care at
writing time changes that.

