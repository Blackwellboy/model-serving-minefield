# Adjudication pass 2: split H30-22 into two upstream XGrammar/speculative mechanisms

**Date:** 2026-08-30

This pass resolves the primary-source follow-up for H30-22. It does not change the canonical Minefield trap count.

## Why H30-22 was split

The Mia GLM-5.3 recipe's pinned `overlay/patch_xgrammar_termination.py` is not one home-grown fix. It explicitly backports two separate merged vLLM changes:

1. vLLM PR #52805 / merge `12f64b39d29282437e35be9aa5db432fb2a1a6e6`
2. vLLM PR #53046 / merge `c6e19b3be24338759a443e03c8325d76da9ee202`

Those patches sit on the same broad axis — structured-output state during speculative decoding — but own different state transitions. Treating them as one H30 mechanism would make the public claim less precise than the primary source.

## H30-22a -> U40

**Entry:** `upstream/U40-vllm-xgrammar-spec-batch-continues-after-termination.md`

Primary source: vLLM issue #52767 + merged PR #52805.

The issue reports that when a structural tag is actually built and MTP speculation is enabled, XGrammar can receive another token after its matcher has already terminated on a stop token. The reporter's controlled matrix found the warning only in the MTP arms; tool calls remained correct in the tested payloads, so the original user-visible impact was deliberately not overstated.

PR #52805 fixes the underlying cached-state/batch behavior:

- `_is_terminated` is updated after each accepted token instead of after the whole list;
- the batch breaks immediately once the matcher terminates;
- validation stops at termination;
- reset clears the cached termination flag.

The PR's stated live test aligned EOS with an early MTP draft slot and left later draft tokens in the same speculative batch. It reports the matcher warning before the fix and clean repeated requests after it.

**Disposition:** upstream-reported, maintainer confirmed, closed/fixed. No first-party Blackwellboy reproduction.

## H30-22b -> U41

**Entry:** `upstream/U41-vllm-spec-reasoning-end-crosses-grammar-activation-window.md`

Primary source: merged vLLM PR #53046.

This is the opposite state transition from U40. The speculative window straddles the end of reasoning. Some tokens in that draft were proposed before structured-output grammar became active. Once the reasoning-end marker occurs, the old path could try to directly advance the newly active grammar using a draft token generated under the earlier no-grammar state, creating spurious `Failed to advance FSM` errors.

PR #53046 changes the post-reasoning-end-in-window arm to validate the token against the now-active grammar before committing it. A stale-to-the-new-state draft is therefore rejected as a speculative proposal rather than treated as a grammar failure.

**Disposition:** upstream-reported, maintainer confirmed, closed/fixed. No first-party Blackwellboy reproduction.

## Dedupe against U32

U32 is not the owner of either mechanism.

U32 covers SGLang speculative finish-state ordering when one accepted run contains EOS/stop **and crosses the output length cap**, which can preserve tokens after an in-budget stop.

U40 is vLLM/XGrammar matcher lifecycle inside a speculative token batch; it needs no length-cap crossing.

U41 is vLLM grammar activation after a reasoning-end marker inside a speculative window; the central problem is that drafts were proposed under the pre-grammar state and are being consumed under the post-boundary state.

The common word "stop" or the common use of speculative decoding is not sufficient to merge these owners.

## Registry effect

`CANONICAL_TRAP_COUNT_IMPACT=0`

`UPSTREAM_PROMOTIONS=U40,U41`

H30-22 should no longer appear in the active primary-source-review queue. Future work on this axis should reference U40 and U41 separately.
