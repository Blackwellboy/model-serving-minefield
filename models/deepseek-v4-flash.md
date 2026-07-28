# DeepSeek-V4-Flash (DSpark, community-abliterated) on vLLM, 2x DGX Spark GB10

First-party coverage of a serving path that, as far as we can tell, nobody else
publishes on. Everything below was measured against a live production lane on
2026-07-28 at request level only: no restarts, no config changes, no container
operations. Where a number has conditions, the conditions are next to it.

## Scope, and what this page is not

This is an **abliterated community re-upload**, not stock DeepSeek V4-Flash.
The checkpoint's own metadata records the edit: a direct FP8 edit of the
attention output projection (`wo_b`) across layers 10 to 42, thirty-three
tensors, relative Frobenius change 0.049 to 0.067 per tensor, one refusal
direction, multi-token-prediction head deliberately left unedited. Its author's
note records that LoRA abliteration was ineffective on this family.

Nothing here should be read as a claim about stock DeepSeek V4-Flash. That
caveat is not boilerplate: the edit targets attention output projections in
thirty-three of forty-three layers, which is not obviously irrelevant to the
long-range attention behaviour this page measures. See
[trap 14](../traps/versioning/14-finetune-reupload-not-drop-in.md) for why a
re-upload is its own artifact.

## The serving path

Read from the running container, not from a launcher script or documentation.

| | |
|---|---|
| Engine | vLLM `0.21.1rc1.dev339+g1967a5627bc3`, V1 engine |
| Hardware | 2x DGX Spark GB10, arm64, CUDA 13, unified memory 121 GiB per node |
| Parallelism | tensor parallel 2 across two nodes, pipeline parallel 1 |
| Weights | FP8 block quantisation, 128x128 blocks, e4m3, ue8m0 scales |
| KV cache | **`nvfp4_ds_mla`**, block size 256, 2,971,484 tokens allocated (21.8 GiB) |
| Attention | MLA with a sparse indexer, `index_topk` 512, 64 index heads |
| Speculative decode | model's own MTP head, depth 3, `draft_sample_method` probabilistic |
| Context | `max_model_len` 1,048,576, requires `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` |
| Trained context | **65,536**, YaRN factor 16 (`rope_scaling` in the checkpoint) |
| Scheduling | chunked prefill on, `--max-num-batched-tokens` 8192, `--max-num-seqs` 4 |
| Prefix caching | **on** |
| Template | none in the checkpoint; a Python encoder via `--trust-remote-code` |
| Thinking | off by default (`--default-chat-template-kwargs {"thinking": false}`) |
| Sampling | serve line overrides generation config to temperature 0.0, top_p 1.0 |

## Traps observed on this model and stack

| Trap | One line | Status |
|---|---|---|
| [the advertised window fails silently](../traps/evaluation/61-advertised-window-fails-silently.md) | 1M advertised, 64K trained, cold retrieval unreliable from 32K, no error ever | reproduced here (the three-ceiling arithmetic) + measured here, raw not published (the curve) |
| [cold prefill and cache hit disagree](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md) | the identical long prompt answers correctly warm and wrongly cold | measured here, raw not published |
| [checkpoint ships no chat template](../traps/template/56-checkpoint-ships-no-chat-template.md) | nothing to hash; no system role delimiter; late system messages weld onto the user turn | reproduced here |
| [thinking kwarg truthiness](../traps/reasoning/57-thinking-kwarg-truthiness-coercion.md) | `"false"` as a string turns thinking on | reproduced here |
| [reasoning_effort is a thinking switch](../traps/reasoning/58-reasoning-effort-injects-hidden-preamble.md) | top-level enables reasoning and injects 79 hidden tokens; the same key in kwargs is ignored | reproduced here |
| [reasoning round-trip confabulation](../traps/reasoning/59-reasoning-roundtrip-confabulation.md) | history reasoning is stripped, and the model confidently quotes it anyway | reproduced here |
| [spec-decode garble](../traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md) | corrupted markup frames under the wrong drafter config | reproduced here (the fixed config and the check) + measured here, raw not published (the failure) |
| [01](../traps/reasoning/01-reasoning-field-two-names.md) | reasoning is written under `reasoning`; `reasoning_content`, this vendor's own API name, does not exist here | confirmed here |
| [04](../traps/template/04-history-reasoning-stripping.md) / [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md) | prior reasoning stripped under both names and four preservation kwargs | confirmed here |
| [12](../traps/evaluation/12-empty-content-at-token-ceiling.md) | HTTP 200, `finish=length`, empty content, reasoning populated | confirmed here |
| [16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md) | inverted here: `stop` to `length` is the earliest degradation signal | confirmed, with a twist |
| [21](../traps/versioning/21-no-generation-config-server-defaults-win.md) | checkpoint ships `do_sample: true, temperature: 1.0`; the serve line overrides to greedy | confirmed here |
| [28](../traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md) | the lane carries a bind-mounted drafter patch whose sole purpose is a concurrency-above-one crash guard | upgraded: previously upstream-reported for this family, now evidenced on our hardware |
| [29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) | server thinking-off is a default; two independent client routes through it | confirmed here |

## Measured: speculative decode acceptance by task family

Single production serve. **There is no baseline arm**: MTP cannot be disabled
without restarting the lane, and this lane does not go down. These are
descriptive acceptance numbers, **not a speedup claim**, and no comparison is
made against any remembered or published baseline.

30 requests, six repeats per family, families interleaved and rotated so no
family sat at a fixed position in the cycle. Counters are Prometheus
`spec_decode` deltas taken immediately either side of each request. An idle
control over 45 seconds showed zero drift on all three counters, so the deltas
are this session's traffic and nothing else's. Drafter depth is 3.

| family | acceptance | accepted per step | pos 0 | pos 1 | pos 2 | decode tok/s | TTFT s |
|---|---|---|---|---|---|---|---|
| tool call | **0.978** | 2.94 / 3 | 0.991 | 0.981 | 0.963 | 39.9 | 0.47 |
| code | 0.857 | 2.57 / 3 | 0.953 | 0.854 | 0.763 | 37.4 | 0.36 |
| math | 0.749 | 2.25 / 3 | 0.888 | 0.736 | 0.624 | 33.1 | 0.42 |
| structured JSON | 0.673 | 2.02 / 3 | 0.867 | 0.653 | 0.499 | 32.1 | 0.40 |
| prose | **0.441** | 1.32 / 3 | 0.690 | 0.437 | 0.197 | 23.9 | 0.42 |
| **all 30 requests** | **0.680** | **2.04 / 3** | 0.856 | 0.672 | 0.512 | n/a | n/a |

**The aggregate is close to meaningless, and that is the finding.** Acceptance
across the whole run is 0.680 at 2.04 accepted tokens per step. Per family it
spans 0.441 to 0.978, a factor of 2.2. Any single headline acceptance number
for a lane is really a statement about the traffic mix that was used to measure
it. A lane benchmarked on tool calls and a lane benchmarked on prose will report
very different acceptance for identical hardware, weights and configuration.
Publish the mix or the number is not interpretable.

Two secondary observations. Acceptance decays monotonically with draft position
in every family, and prose loses the third token four times out of five, so the
marginal value of depth is strongly task-dependent, which is the same shape as
[trap 11](../traps/runtime/11-speculative-depth-peak-and-collapse.md). And
decode throughput tracks acceptance closely across families, from 23.9 tok/s at
the low end to 39.9 at the high end.

## Measured: temperature-zero determinism is task-dependent

Worth its own note because it undermines a common assumption. The serve line
pins temperature to 0.0 and top_p to 1.0, so every request above was greedy.

**Observation: measured.** Of the six repeats per family, prose, JSON and
tool-calling prompts returned **byte-identical** completions all six times. The
code prompt returned four distinct outputs in six runs (completion lengths 114,
107, 114, 157, 160, 160) and the maths prompt likewise. Same prompt, same greedy
settings, same lane, same session.

**Cause: hypothesis, not established.** The most likely explanation is the
probabilistic draft sampling the speculative decoder runs with. **It was not
isolated, and no competing explanation was excluded.** Isolating it requires
changing the drafter configuration, which is a serve change this lane does not
permit. Do not cite this as a demonstrated property of probabilistic draft
sampling; cite it as an unexplained, task-dependent variance floor on this lane.

**Two consequences, both load-bearing elsewhere on this page.** First,
"temperature 0, therefore reproducible" is false here for some task types, so
any n=1 result on this lane, including any of ours, should be read with that in
mind. Second, it is exactly why the cold-versus-warm cache claim in
[cold prefill and cache hit disagree](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md)
rests on a 10-versus-10 separation across six prompt lengths and seven
documents **rather than on any single cold/warm pair**. With a non-zero noise
floor that we cannot yet explain, a single pair would not have carried that
claim, and the entry says so.

## Measured: cold-prefill context depth curve

Full curve, method and caveats in
[the advertised window fails silently](../traps/evaluation/61-advertised-window-fails-silently.md).
Headline: a fact planted at prompt position zero is recovered reliably to
16,000 tokens with a clean stop; from 32,000 the model stops emitting a stop
token and runs to the cap; recovery becomes unreliable rather than failing at a
threshold, with failures at 60,000, 100,000, 131,072 (twice) and 262,144 and
successes at 65,536, 70,000 and 524,288. The server's reported `prompt_tokens`
matched an independent local tokenization **exactly at every depth including
the million-token runs**, so nothing is silently truncated and the token
accounting can be trusted.

At the advertised context the answer has a condition attached. A fully cold
999,996-token request returned no first token inside a 1,800 second client
timeout. The same document at 79% prefix reuse failed, opening with the first
word of the planted passphrase and then fabricating the rest. The same document
at 99.99% reuse was answered **correctly in seven tokens with a clean stop**.
So the million-token window is real and the head of the prompt is genuinely
reachable; whether you get it depends on a server-side cache condition that
appears in no request and no response.

**Incomplete measurement, flagged:** there is no *completed* fully-cold result
at a million tokens. The cold attempt was abandoned at the timeout and could not
be retried cold, because that attempt had itself cached roughly 794,000 tokens
of the document and forcing a genuine cold repeat would have meant displacing
almost the entire 2,971,484-token KV cache on a production lane. The
million-token evidence is therefore a 79%-versus-99.99% contrast; the
cold-versus-warm contrast rests on the 131K, 262K and 524K pairs, where the cold
arm is a measured 0.0% hit.

## The registry doctor against this stack

Run read-only at registry commit `6a2e0e6`, the hardened revision. Recorded
because this was a real-world test of that hardening against a stack it had
never seen. Coverage line as printed at that commit, when the registry held 42 entries:
*implemented 17 of 42, executed on this stack 13, clean 6, problems 7,
inconclusive 4, not implemented 25*. The registry has grown since; the
denominator here is a record of what that run saw, not a current count.

**It got the substance right.** All four problems it raised were independently
confirmed by our own probes: the thinking-kwarg override, history reasoning
stripping with no working preservation path (it tried both field names plus
four preservation kwargs, which is more than we did), the empty-content ceiling,
and it correctly identified that reasoning is exposed under `reasoning` rather
than the other name. It also established the lane is text-only by probing and
getting a 400 that named the modality, rather than assuming.

**The hardening earned its keep.** Its "could not check" on kwarg deadness is
exactly right and would have been a false CLEAN before commit `6a2e0e6`: it
reported that it could not read a chat template on this stack and therefore
could not determine whether any kwarg is read. That is the correct verdict, and
it is the correct verdict *because of* the no-template-file trap above. A tool
that had guessed would have been wrong.

**Two findings for the doctor's maintainer.**

*One, an internal inconsistency.* The same run used
`/v1/chat/completions/render` plus `/detokenize` successfully for the trap 04
and 25 history checks, then declared for trap 07 that "no chat template is
readable on this stack (llama.cpp `/props` is the only source this tool has)".
It has a working render path and does not reach for it in that check. Its
suggested remedy, "fetch the checkpoint's `chat_template.jinja`", is
**unactionable here**: no such file exists in this checkpoint, and no amount of
fetching will produce one. On this family the remedy needs to be "render the
prompt through the server", which the tool already knows how to do.

*Two, a true observation carrying a wrong verdict.* It flagged the assembled
prompt as having two closing think tags against one opening tag, titled
"orphaned close tags in history", with the fix "fix template or history
assembly". The observation is accurate. The verdict is not: on this family a
closing think tag is how a thinking-off assistant turn *opens*, so the
imbalance is by design and there is nothing to fix. A tag-balance heuristic is
a good detector on stacks where the opening tag is the delimiter, and a false
positive on stacks where the closing tag is a turn marker. Worth a
family-conditional note rather than a flat problem.

Neither of these is a reason to distrust the run. The tool was honest about its
own coverage, and the two issues above are both cases where it reported
*something* rather than silently passing.

## Reproducing any of this

Harnesses used are small and self-contained: a depth-curve generator with a
planted fact and unique non-repeating filler, a cold/warm repeat driver that
records prefix-cache hit deltas per request, an interleaved MTP acceptance
driver that deltas the Prometheus counters, and a probe sweep. All request
level. Nothing here needs privileged access to a lane; the configuration
forensics needs read access to the container and the checkpoint.
