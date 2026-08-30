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
| [U17, client stop strings fire inside reasoning and erase the answer](U17-vllm-stop-strings-fire-inside-reasoning.md) | vLLM / DeepSeek V4 | maintainer confirmed | closed, fixed |
| [U18, empty tool_calls deltas hide valid streamed text](U18-vllm-empty-tool-calls-delta-hides-content.md) | vLLM / agent clients | maintainer confirmed | closed, fixed |
| [U19, shared multi-node JIT caches corrupt generated build products](U19-multinode-shared-jit-cache-corrupts-build-products.md) | vLLM / multi-node | maintainer confirmed | closed, fixed |
| [U20, a direct GB10 QSFP pair can use only one of two NICs](U20-gb10-direct-qsfp-single-hca-half-bandwidth.md) | DGX Spark / NCCL | maintainer confirmed | closed, fixed |
| [U21, speculative stream chunks are decode steps, not token counts](U21-spec-decode-stream-chunks-are-not-tokens.md) | vLLM / speculative decode | maintainer confirmed | closed, fixed |
| [U22, the DSpark draft loader silently drops shared-expert weights](U22-dspark-loader-silently-drops-shared-expert-weights.md) | vLLM DSpark / DeepSeek V4 | maintainer confirmed | closed, fixed |
| [U23, invalid padding indices can drive a sparse-KV gather out of bounds](U23-deepseek-sparse-index-padding-token-oob.md) | vLLM / DeepSeek V4 | maintainer confirmed | closed, fixed |
| [U24, stale DSpark slot ids can kill the engine at request condensation](U24-dspark-stale-slot-id-after-request-condensation.md) | vLLM DSpark | maintainer confirmed | closed, fixed |
| [U25, naive uniqueness metrics can call a reasoning loop fresh text](U25-loop-detector-block-uniqueness-misses-templated-loops.md) | evaluation / reasoning traces | maintainer confirmed | closed, fixed |
| [U26, EngineDead can still exit the serving container with code 0](U26-vllm-enginedead-container-exits-zero-and-stays-down.md) | vLLM / Docker | maintainer confirmed | closed, fixed |
| [U27, draft counts above four can leave stale DSV4 compressed state](U27-sglang-dsv4-spec-draft-over4-stale-compress-state.md) | SGLang / DeepSeek V4 | maintainer confirmed | closed, fixed |
| [U28, a prefix-cache hit can restore another request's conv state](U28-sglang-prefill-graph-stale-track-prefix-cache.md) | SGLang / hybrid SWA-Mamba | maintainer confirmed | closed, fixed |
| [U29, unified memory + Triton + deterministic inference can mix KV id spaces](U29-sglang-unified-triton-deterministic-virtual-physical-kv.md) | SGLang | maintainer confirmed | closed, fixed |
| [U30, recycled unified-memory page tails can leak historical bytes](U30-sglang-unified-page-recycle-stale-tail.md) | SGLang / DSPARK | maintainer confirmed | closed, fixed |
| [U31, 32-bit slot-stride multiplication can wrap recurrent state addresses](U31-sglang-int32-slot-stride-wrap-recurrent-state.md) | SGLang / DSPARK | maintainer confirmed | closed, fixed |
| [U32, a speculative accept run can leak tokens after EOS at the length cap](U32-sglang-spec-stop-eos-crosses-length-cap.md) | SGLang / speculative decode | maintainer confirmed | closed, fixed |
| [U33, missing DFlash causality metadata can change semantics after an update](U33-sglang-dflash-missing-is-causal-default-drift.md) | SGLang / DFlash | maintainer confirmed | closed, fixed |
| [U34, DFlash draft-KV budgeting can undercount by the DCP factor](U34-sglang-dflash-dcp-draft-kv-budget-undercount.md) | SGLang / DFlash / DCP | maintainer confirmed | closed, fixed |
| [U35, a resolvable dependency set can still make FA4 fail on Blackwell](U35-sglang-fa4-blackwell-resolved-deps-still-fail-compile.md) | SGLang / FA4 / Blackwell | maintainer confirmed | closed, fixed |
| [U36, warm-restart startup-hook stdout corrupts launcher JSON](U36-glm53-warm-restart-sitecustomize-stdout-corrupts-json.md) | GLM-5.3 / vLLM / Python launcher | maintainer confirmed | closed, fixed |
| [U37, long cold prefill starves a peer decode without preemption](U37-glm53-cold-prefill-starves-peer-decode-without-preemption.md) | GLM-5.3 / vLLM / DGX Spark | maintainer reproduced | closed, fixed |
| [U38, grouped DFlash block IDs make global KV-token capacity non-fungible](U38-glm53-dflash-block-id-tax-makes-kv-token-capacity-nonfungible.md) | GLM-5.3 / DFlash2 / grouped KV | maintainer reproduced | closed, fixed |
| [U39, ModelOpt NVFP4 can emit invalid byte-token sequences on SM120](U39-vllm-modelopt-nvfp4-invalid-byte-token-ids-sm120.md) | vLLM / ModelOpt NVFP4 / SM120 | none | open |
| [U40, XGrammar speculative batches can advance after matcher termination](U40-vllm-xgrammar-spec-batch-continues-after-termination.md) | vLLM / XGrammar / MTP | maintainer confirmed | closed, fixed |
| [U41, reasoning end can activate grammar inside a speculative window](U41-vllm-spec-reasoning-end-crosses-grammar-activation-window.md) | vLLM / reasoning / XGrammar / spec decode | maintainer confirmed | closed, fixed |

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

U17-U26 came from a 2026-08-21 review of the current
`tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark` tree and its
merged PR/issue evidence. The pass deliberately did **not** turn every source
claim into an upstream entry: reasoning-field and reasoning-effort findings
extend existing canonical traps 01 and 07; the unresolved CUBLAS engine-death
root cause, non-default-port health-check bug, fragmented-loop limitation and
other secondary leads remain in
[`mining/2026-08-21-tonyd2wild-deepseek-v4-community-harvest.md`](../mining/2026-08-21-tonyd2wild-deepseek-v4-community-harvest.md).

U27-U35 came from the 2026-08-25 SGLang v0.5.18 source-mining pass. Each entry
is backed by a merged SGLang PR with a concrete source-level mechanism, but none
has been reproduced by this registry. The exact promotion map and duplicate
boundaries are recorded in
[`mining/2026-08-25-sglang-upstream-promotion.md`](../mining/2026-08-25-sglang-upstream-promotion.md).
The community `glm52-spark-kit` and `veloGB10` findings from the same harvest
remain in the lead/adjudication path rather than being silently upgraded.

U36-U41 came from the 2026-08-30 GLM-5.3 / Ling-3.0 / Qwen3.8 GB10 harvest and its source-level adjudication passes. H30-10, H30-11 and H30-12 were reopened against current primary tracker threads and fixed source before promotion. H30-08 was reopened against vLLM #54150 and promoted only as an open unresolved behavior report, with damaged conversion versus ModelOpt loader path left explicitly unsettled. H30-22 was split instead of promoted as one compound item: vLLM PR #52805 owns speculative XGrammar batches continuing after matcher termination (U40), while PR #53046 owns a separate reasoning-end transition where the grammar activates inside a speculative window and pre-transition draft tokens must be validated before advance (U41). None of U36-U41 is a first-party Blackwellboy reproduction, and the remaining H30 findings stay in the mining/adjudication queue until their own evidence bars are met.

The procedural rule from the first pass still holds: **the mining summary is a lead, not the source.** Read the current tracker thread, preserve corrections
and retractions, and record resolution state before promoting anything here.
