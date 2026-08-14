# Upstream-reported: real reports, on stacks we cannot run

**Nothing in this directory has been reproduced here.** Every entry is a report
from somebody else's issue tracker or vendor channel, on a stack, a model or a
hardware class we do not have. We read the thread, recorded who reported it,
whether a maintainer engaged, and what state the issue is in, and we wrote down
what you would run to settle it.

That is a weaker claim than anything under [`traps/`](../traps/), and the
directory exists so that the difference is obvious at a glance rather than
buried in a status line. The tier and its enforced requirements are defined in
[CONTRIBUTING](../CONTRIBUTING.md#the-fourth-tier-upstream-reported).

**These entries never appear in [Core](../CORE.md), never count toward
[doctor](../doctor/) coverage, and never count toward the registry total.**
Those three separations are asserted by
[`integrity/upstream_integrity.py`](../integrity/upstream_integrity.py) on
every run, not observed by convention.

## Why publish at all

A maintainer-confirmed bug with a reproduction in the thread will cost somebody
an evening whether or not we ran it. Sitting on it because we lack the hardware
helps nobody, and it is the reason roughly fifty mined candidates sat
unpublished. Publishing also creates the thing a private queue cannot: a place
for a reader who **does** have the stack to confirm or refute it. Every entry
ends with what to run and what would settle it either way.

## How to read the two labels that carry most of the weight

**Maintainer engagement.** `maintainer reproduced` is the strongest thing this
tier says and it means exactly that: somebody with commit rights reproduced it
in the thread. `maintainer disputed` is recorded just as plainly, and one entry
here carries it.

**Issue state.** `closed, not fixed` is not `closed, fixed`. Two entries here
were closed by a staleness bot while a maintainer reproduction and a
`high priority` label were still attached. A closed tab is not a fixed bug.

## The entries

| Entry | Stack | Engagement | Issue state |
|---|---|---|---|
| [U01, tool calls vanish from the rendered prompt on one of two routes](U01-ollama-toolcalls-missing-on-openai-route.md) | Ollama | maintainer confirmed | open |
| [U02, sampling penalties are accepted and discarded](U02-ollama-go-runner-drops-sampling-penalties.md) | Ollama | maintainer disputed | open |
| [U03, the bundled template is not the model's template](U03-ollama-bundled-template-diverges.md) | Ollama | maintainer confirmed | open |
| [U04, a minor version moved the default context by 64x](U04-ollama-vram-tiered-default-context.md) | Ollama | maintainer responded | closed, not fixed |
| [U05, an empty think block turned tool calls into raw JSON](U05-ollama-gemma4-think-false-leaks-json.md) | Ollama | maintainer confirmed | closed, fixed |
| [U06, native tool markup with an empty tool_calls array](U06-mlx-lm-gemma4-tool-parser-missing.md) | mlx_lm | maintainer confirmed | closed, fixed |
| [U07, a valid-looking tool call with contaminated arguments](U07-sglang-tool-choice-required-contaminates-args.md) | SGLang | maintainer confirmed | open |
| [U08, one extra channel and the chat endpoint throws](U08-sglang-harmony-commentary-channel-valueerror.md) | SGLang | maintainer reproduced | closed, not fixed |
| [U09, the chat template you passed was ignored, with a warning you did not see](U09-vllm-mistral-chat-template-ignored.md) | vLLM | maintainer confirmed | closed, fixed |
| [U10, a reranker with no template returns confident, near-reversed scores](U10-vllm-vl-reranker-without-chat-template.md) | vLLM | maintainer responded | closed, resolved as usage |
| [U11, tool output renders empty and the model calls the tool forever](U11-glm-tool-content-array-renders-empty.md) | vLLM, SGLang | maintainer confirmed | closed, fixed |
| [U12, streaming validation commits HTTP 200 before rejection](U12-sglang-streaming-validation-http200.md) | SGLang | maintainer confirmed | closed, fixed |
| [U13, iSWA cache reuse needs full SWA KV retention](U13-llamacpp-iswa-cache-reuse-needs-swa-full.md) | llama.cpp | maintainer confirmed | closed, resolved as usage |
| [U14, separate chat_template.jinja is not loaded](U14-tgi-separate-chat-template-jinja-not-loaded.md) | TGI | none | open |
| [U15, an MTP-labelled checkpoint does not prove MTP is executed](U15-mlx-mtp-label-does-not-prove-mtp-runtime.md) | mlx_lm | none | open |
| [U16, MTP corrupts output at a concurrency/batch boundary](U16-vllm-mtp-corrupts-at-concurrency-boundary.md) | vLLM | none | open |

## Where these came from, and what did not survive

U01-U11 came from a fifty-candidate desk-mining round worked in full on
2026-07-28. The classification table, including the twenty-two candidates
closed as too weak and the corrections to candidates whose mining summary
misstated the thread, is in
[the classification note](../mining/2026-07-28-r2-queue-classified-upstream-tier.md).

U12-U16 came from a second recovery pass on 2026-08-14 over Blackwellboy's
historical private Minefield promotion queue. Every original lead was reopened
against its current public issue/PR before publication. That changed important
parts of the record: SGLang #19996 is now fixed by a merged regression PR; the
llama.cpp cache-reuse report resolved to an iSWA state-retention requirement;
TGI is archived; MLX's original speculative-EOS hypothesis was narrowed by
loader source inspection; and vLLM's MTP corruption report accumulated
additional cross-hardware evidence while the root cause remained unresolved.
The audit trail is in
[`mining/2026-08-14-upstream-candidate-refresh.md`](../mining/2026-08-14-upstream-candidate-refresh.md).

The procedural rule from the first pass still holds: **the mining summary is a
lead, not the source.** Read the current tracker thread, preserve corrections
and retractions, and record resolution state before promoting anything here.
