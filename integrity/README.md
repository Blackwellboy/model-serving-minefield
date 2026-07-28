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

