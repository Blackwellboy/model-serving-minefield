# Reading an upstream thread before citing it as a primary

**Date:** 2026-07-29
**Kind:** methodology, ours. Not a serving trap.

## Why this is here and not in `traps/`

`traps/` documents failures in serving stacks that cost an operator time. This
is a failure in **our own vetting**, and its victim is a reader who trusts a
citation we published. It has no lane, no config and no reproduction on
hardware. Filing it as a trap would put a research-process defect in a registry
of serving defects and dilute both, so it lives here, next to the queue whose
handling produced it.

## The defect

A desk-mined candidate is described in its own summary as a live engine bug.
The upstream thread it points at was closed by the reporter as **his own usage
error**. Cite it as a primary and we publish, under our name, a claim the
source itself withdrew.

**This is the second instance.** The first is recorded in the
[CHANGELOG](../CHANGELOG.md) for 2026-07-28: of the round-2 queue candidates
that had a real source, several were materially misdescribed by their own
summaries, including two described as live engine bugs that the thread had
closed as usage. That finding is what produced the `upstream/` evidence bar.

The second instance got past that bar. A candidate was proposed as the class
primary for a hang report, rated high confidence, on the strength of "comments
explicitly recommend" two specific flags. All of that was literally true and
the citation was still wrong.

It was caught only because the session was told not to take the match on trust.
A bar that depends on someone being told that is not a bar.

## The check

Before citing an upstream issue as a primary, read three things that are not
the issue body.

**1. `author_association` on every comment.** Not the tone, not the confidence,
the field. GitHub returns it per comment. `NONE` means the commenter has no
association with the project. A thread can be long, technical, confident and
contain zero project voices.

```bash
gh api "repos/OWNER/REPO/issues/N/comments?per_page=100" \
  --jq '[.[] | select(.author_association != "NONE")] | length'
```

If that returns `0`, the engagement value is `none`. It is not
`maintainer responded` because somebody helpful turned up.

**2. Who closed it, and when.** The issue-level `state_reason` is not enough.
`completed` is written by GitHub for any non-`not_planned` close, including a
reporter closing his own report.

```bash
gh api "repos/OWNER/REPO/issues/N/timeline?per_page=100" \
  -H "Accept: application/vnd.github+json" \
  --jq '.[] | select(.event=="closed") | "\(.event) by @\(.actor.login) at \(.created_at)"'
```

If the actor is the reporter, the issue is a self-close and is **not** a
confirmed defect until something else says so.

**3. What the closer said immediately before closing.** This is the one that
catches the case. A self-close usually has a final comment explaining it, and
that comment is where "I had a conceptual error" lives.

## The two rules that fall out

- **A recommendation from a `NONE`-level commenter, posted after the close, is
  not maintainer engagement.** It is a stranger's workaround on a dead thread.
  It may even be correct. It is not the project agreeing with the report, and
  our engagement vocabulary has no value that means "somebody said this once".
- **A self-closed issue is not a confirmed defect.** Under our
  [issue-state vocabulary](../CONTRIBUTING.md#the-fourth-tier-upstream-reported)
  a reporter closing his own report after concluding he misunderstood the
  system is closest to `closed, resolved as usage`, which is the value that
  exists precisely so this cannot be filed as `closed, fixed`.

## The worked example

`vllm-project/vllm#33041`, "[Bug]: vLLM hangs after NCCL init with TP=2 on
Blackwell GPUs". Recorded here with its disposition so it cannot be
re-proposed, and so the reasoning is checkable rather than asserted.

| Surface reading | What the thread actually shows |
|---|---|
| Closed, `state_reason=completed` | Closed **by the reporter**, 2026-01-26, three minutes after he wrote that he had made a conceptual error about how vLLM works |
| "Comments recommend `NCCL_P2P_DISABLE=1` and `--disable-custom-all-reduce`" | **One** comment does, from a `NONE`-level account, **102 days after the close**, linking that account's own repository |
| "Plus IOMMU and ACS workarounds" | Suggested by another `NONE` account; the reporter replied that it did not fix his case |
| Maintainer engagement | **Zero.** All nine comments are `author_association: NONE` |

Verdict: **not usable as a primary.** Engagement `none`, state closest to
`closed, resolved as usage`.

For contrast, `vllm-project/vllm#17676` is open, has three `CONTRIBUTOR`-level
commenters, and one of them reports the same flag working only sometimes. That
is real project-adjacent engagement on the class. It is also a broader issue
than the report it was proposed for, which is why it was cited as context and
not as a primary.

## What this does not change

The `upstream/` bar already required a primary source read, an issue state and
an engagement value from closed vocabularies. Nothing in that was wrong. What
was missing is that reading a source was treated as opening the page, when the
three fields above are what the page does not say out loud.