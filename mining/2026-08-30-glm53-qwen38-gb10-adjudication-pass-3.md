# Adjudication pass 3: H30-19 remains unresolved

**Date:** 2026-08-30

This pass reopens the primary issue behind H30-19 and records the finding at the weakest public tier matching the evidence. It does not change the canonical Minefield trap count.

## H30-19 -> U42

Entry: `upstream/U42-glm53-blank-required-tool-args-only-under-production-state.md`

Primary source: MiaAI-Lab GLM-5.3 EXL3 issue #10 and its maintainer investigation comments.

The reporter documented a production-state failure where some parsed tool calls carried a function name but blank or missing required arguments. A captured byte-identical request reportedly failed repeatedly in production but stayed clean across 15+ standalone replays. A heavier synthetic produced one malformed returned call amid many timeouts.

MiaAI-Lab then ran 53 synthetic cases on its 2x GB10 recipe and saw zero blank required arguments and zero timeouts. The maintainer also ruled out a process-wide glm47 parser-state table because parser state is constructed per request.

The maintainer noted that a final parsed empty argument object is not enough to identify the failing layer. It can arise because generation omitted arguments, generation ended mid-call, a client timed out or aborted, or streaming finalization closed an incomplete call. The sequential TC-43 empty-query result was also separated from this concurrency report as a different mechanism.

The decisive artifact is still missing: one failing production turn preserving raw generated text or token IDs together with finish reason, completion budget, timeout state, streaming mode and cache state. Until that exists, DFlash2, prefix caching, batching and glm47 remain test variables rather than established causes.

U42 is therefore intentionally `upstream-reported`, `maintainer responded`, and `open`, with the maintainer's 53-case non-reproduction attached to the claim.

## Registry effect

`CANONICAL_TRAP_COUNT_IMPACT=0`

`UPSTREAM_PROMOTIONS=U42`

H30-19 leaves the mining-only queue, but U42 remains unresolved until a failing raw artifact or a discriminating A/B localizes the failure.
