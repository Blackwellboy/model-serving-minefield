# R2-31: DeepSeek V4 system-message default (no quality cliff at small n)

**Candidate:** mining round 2, R2-31 (vLLM issue 46710: system message
handling default leaves system messages in place; claimed incorrect output).

**Verdict here:** DOES NOT REPRODUCE at this scale. No system-dependent
quality change on the production DeepSeek V4 Flash lane.

**Date:** 2026-07-27. Verification used 15 read-only probes to the
production lane, pre-authorized by the verification queue's hardware note
for this candidate. No serve-config changes, no container changes.

## Test surface

Production DeepSeek V4 Flash abliterated lane (two-node DGX Spark pair,
vLLM, max_model_len 1048576). This is the exact hardware class the round-2
queue names for this candidate.

## Probe

Three arms x 5 exact-answer prompts, temperature 0, max_tokens 4096:

1. no system message
2. short system ("You are a helpful assistant.")
3. long directive system (precision plus formatting instructions)

## Results

| Arm | Correct | Notes |
|-----|---------|-------|
| none | 4/5 | miss: backwards-spelling prompt |
| short | 4/5 | identical miss |
| long | 4/5 | identical miss |

The single miss is the same near-correct answer in all three arms:
"dleif enim" (spurious space inside an otherwise correct reversal). It is a
model capability wobble, fully system-independent. The long-system arm
actually tightened formatting (bare "dleif enim" with no wrapper sentence),
i.e. the system message is being honored, not corrupting output.

## Scope of this negative

Small n, short easy prompts, single model build. The upstream issue may
require specific templates, long contexts, or multi-turn shapes not
exercised here. Status: no evidence of a system-message quality cliff on
this lane; not promoted; candidate stays open pending a reproduction recipe
from the upstream issue.

Evidence: probe rows in the same 55-row archive as the
[R2-39 note](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md);
available on request.
