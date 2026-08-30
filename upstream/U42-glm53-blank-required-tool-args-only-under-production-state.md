# U42: required tool arguments can disappear in production state while byte-identical solo replay stays clean

**Reported by @d3vilbug.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer responded.** MiaAI-Lab investigated the report on its 2x GB10 kit, ruled out a process-wide glm47 parser-state leak, ran 53 synthetic cases without reproducing the blank-argument symptom, and documented the artifacts needed to distinguish generation, truncation/timeout and stream-assembly causes.

**Issue state: open.** The production-state mechanism remains unresolved.

**Primary source.** [MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks issue #10](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/10) and maintainer investigation comments, read on 2026-08-30.

**Symptom.** Under reported production concurrent load, some OpenAI-style tool calls carried the function name but `{}` or otherwise missing required arguments. The reporter captured a byte-identical request that failed repeatedly in production, including a silent retry, yet 15+ standalone replays across streaming/non-streaming and several prompt sizes were clean. A heavier synthetic with cold-prefill peers produced one malformed returned call amid many timeouts, so the visible symptom is correlated with production-like state but the causal owner is not established.

**What the source rules out.** MiaAI-Lab inspected the published recipe and reported that `ParserEngine` is constructed per request, so a process-wide glm47 parse-state table is not the mechanism. It also cautioned that `{}` in the final OpenAI object is not sufficient evidence of model corruption: glm47 can legitimately finish a name-only/unfinished call as `{}` after truncation, timeout or abort, and the sequential TC-43 empty-query eval is a different symptom/mechanism.

**Counterevidence that must stay attached.** MiaAI-Lab ran 53 live synthetic cases spanning c=1/c=4, streaming and non-streaming, thinking on/off, unique long cold prefixes and mixed long+short requests, and observed 0 blank/missing required args and 0 timeouts. That does not refute the reporter's production capture because the maintainer test used different max sequence width, fewer tools, no ~95K shared system prefix, and longer client timeouts, but it means this is **not** a reproduced recipe-wide DFlash or glm47 bug.

**Open mechanism.** A failing parsed `{}` can still come from at least four places: the model emitted no arg XML, generation ended in the middle of a call, the client/stream assembler lost or flushed an arg delta, or a timeout/length finish forced a name-only call through the parser. Speculative decoding, prefix-cache state and production batching remain test variables, not established causes.

**What we have not done.** We have not captured a failing turn with raw assistant token IDs/XML plus finish/timeout/cache state on Blackwellboy infrastructure, so the registry does not blame DFlash2, prefix caching, continuous batching or glm47.

## If you have this stack

On the next failing production turn preserve both pre-parser and post-parser evidence: raw assistant text/token IDs, parsed tool object, `finish_reason`, completion budget/usage, client timeout/abort state, streaming mode, thinking mode, and prefix-cache hits. Replay the same body under the same concurrent state, then A/B speculation off, prefix cache off and non-streaming one variable at a time.

**CONFIRM.** Capture at least one production-state failure where the raw XML/token stream proves whether the argument was absent at generation or lost after generation, and reproduce the same failure class under a matched state while a one-variable control removes it.

**REFUTE.** Every apparent blank-arg case is explained by length/timeout/abort or stream assembly with raw generated arguments intact, or matched production-state replay remains clean across sufficient trials and no raw failing artifact survives.

## Attribution

Reported by @d3vilbug in MiaAI-Lab issue #10. MiaAI-Lab investigated and supplied important negative controls but did not reproduce the reported production failure on its own test matrix. The registry has not independently reproduced it.
