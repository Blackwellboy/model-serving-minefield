# Upstream candidate refresh — 2026-08-14

**Disposition: public-source mining queue, not first-party reproduction. No canonical trap IDs allocated here.**

A wider audit recovered an earlier private promotion queue containing five public upstream serving issues that were not present in current Minefield. Each item was re-checked against its current primary GitHub issue/PR state before being recorded here.

## 1. SGLang: streaming validation error can be HTTP 200

Primary issue: [sgl-project/sglang#19996](https://github.com/sgl-project/sglang/issues/19996)

Final fix: [sgl-project/sglang#21900](https://github.com/sgl-project/sglang/pull/21900), merged.

**Reported behavior:** for an oversized prompt, non-streaming OpenAI-compatible requests returned HTTP 400 while `stream=true` could commit HTTP 200 and then place the validation error in the stream payload.

The merged fix explains the mechanism cleanly: the server returned `StreamingResponse` before the async generator reached validation, so the status code was already committed. The fix advances the generator far enough to surface a pre-stream validation error while an HTTP 400 can still be returned, and adds a streaming context-length regression test.

**Minefield value:** HTTP 200 is not proof that a streaming generation request was accepted successfully; client/harness code must inspect the SSE/error contract as well as transport status on affected builds.

**Current routing:** strong historical `upstream/` candidate. Fixed upstream, so scope must be version/build bounded.

## 2. llama.cpp: `--cache-reuse` does not imply reusable full-prefix state on iSWA

Primary issue: [ggml-org/llama.cpp#15082](https://github.com/ggml-org/llama.cpp/issues/15082), closed.

The reporter saw repeated prompt reprocessing even though `--cache-reuse 1` was present. Maintainer guidance identified the missing condition: for iSWA models, prefix reuse requires `--swa-full`, because the reuse operation needs the full KV state rather than only the sliding-window state. The reporter later confirmed that `--swa-full` resolved the observed cache-reuse failure in their test.

**Minefield value:** a cache-reuse flag can be syntactically enabled while the model's attention/KV policy makes the required reusable state unavailable. Measure actual reused tokens/prefill work; do not infer reuse from the launch flag alone. The workaround has a memory cost because it retains the full SWA KV state.

**Current routing:** strong stack-semantics `upstream/` candidate, not necessarily a software defect in current semantics.

## 3. TGI: separate `chat_template.jinja` can be invisible to the server

Primary issue: [huggingface/text-generation-inference#3247](https://github.com/huggingface/text-generation-inference/issues/3247), still open in the archived TGI repository.

**Reported behavior:** newer Transformers/checkpoint layouts may store the chat template as a separate `chat_template.jinja`. The affected TGI path expected the template in `tokenizer_config.json`, so the server could otherwise load but `/v1/chat/completions` failed with a template-not-found error. A second user reported manually copying/editing the template into tokenizer configuration to make chat completions runnable.

**Minefield value:** checkpoint template location is part of runtime compatibility. "The model loaded" does not prove the chat endpoint found the template artifact the checkpoint actually ships.

**Current routing:** historical `upstream/` candidate. Explicitly note that TGI is archived; this is compatibility evidence, not an expectation of a future upstream fix.

## 4. MLX-LM: MTP-labelled checkpoint behavior did not imply MTP execution

Primary issue: [ml-explore/mlx-lm#1292](https://github.com/ml-explore/mlx-lm/issues/1292)

Related native-MTP work: [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990), open as of this audit.

**Observed issue report:** Qwen3.6 MTP variants could truncate sharply on a repeated-system/new-user prefix pattern while comparable non-MTP variants completed normally. The API response remained structurally valid and reported the short completion truthfully.

Later source inspection in the issue materially narrows the initial speculation hypothesis: multiple MLX-LM model loaders filtered out `mtp.*` weights, so downloading an MTP-labelled checkpoint did not mean those heads were used for speculative decoding. In the affected Qwen path, commenters also identified that presence of MTP weights could influence a norm-shifting sanitation condition even after the MTP tensors were discarded. PR #990 is implementing native MTP support and separates the norm-shift condition from mere MTP-weight presence.

**Claim boundary:** the source facts about discarding MTP tensors and the relevant sanitation predicate are stronger than the original "speculative EOS" hypothesis. This note does not claim that either one alone has been proven as the sole cause of every short completion in #1292.

**Minefield value:** a checkpoint/filename capability label is not runtime evidence. Verify that the serving stack actually consumes the feature weights/path being benchmarked, and distinguish loader sanitation from speculative execution.

**Current routing:** strong `upstream/` candidate with mechanism status still partly unresolved; preserve issue/PR state and exact affected versions if promoted.

## 5. vLLM: MTP correctness can collapse at a concurrency/mixed-batch boundary

Primary issue: [vllm-project/vllm#35288](https://github.com/vllm-project/vllm/issues/35288), open.

The original report shows a strong concurrency interaction: MTP-off and lower-concurrency controls behave normally, while higher concurrency can produce garbage/repetition and requests running to the output cap. The same model/data on another serving stack was reported not to show the same c=4 failure.

Subsequent issue comments broaden the evidence across hardware/version combinations. One report found the break point moved when `max_num_batched_tokens` changed and was much easier to trigger with long prompts, supporting a mixed prefill/decode batch interaction rather than a simple static concurrency number. Another independent report on a newer vLLM image and different NVIDIA GPU saw output duplication/corruption at `max-num-seqs=4` disappear after reducing it to 2.

There are plausible source-level hypotheses in the thread involving MTP state/indexing, hybrid/prefix-cache state and mixed batches, but the issue remains open and the mechanism is not settled.

**Minefield value:** speculative decoding can be throughput-positive at c1 and still be correctness-unsafe at a higher concurrency or mixed-batch shape. A performance qualification therefore needs a correctness check at the concurrency/context regime actually deployed.

**Current routing:** strong reported-by-others `upstream/` candidate; do not publish a definitive root cause yet.

## Dedup result

Exact searches of current public Minefield did not find these issue numbers or an exact owner for the five mechanisms above. Some are adjacent to existing template, cache, speculation and measurement traps, but the upstream records add distinct stack/version-specific checks.

Recommended later promotion shape: dedicated `upstream/Uxx` records first, preserving `reported by others` status and current upstream resolution state. Do not relabel them as Blackwellboy first-party measurements.

`NEW_CANONICAL_TRAP_IDS_IN_THIS_PR=0`
