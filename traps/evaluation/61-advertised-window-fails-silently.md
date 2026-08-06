# Trap 61: a 1M advertised window, a 64K trained window, and a failure that never errors

**Found by Blackwellboy.**

**Status: reproduced here** for the three-ceiling arithmetic (the numbers are
in the checkpoint's own public `config.json`, and steps 1 and 2 of the check
re-derive them), and **measured here, raw not published** for the depth curve,
the throughput figures and the recovery pattern. The two halves do not carry
the same weight and the entry says which is which throughout.

- **Reproduced here** for the three-ceiling arithmetic. Anyone can check it
  without us: the trained length, the extrapolation factor and the product that
  becomes the advertised number are all in the checkpoint's own public
  `config.json` rope-scaling block, and the long-context override variable is
  visible in the serving container's environment on any lane that sets it.
  Steps 1 and 2 of the check below re-derive it from artifacts you can fetch.
- **Measured here, raw not published** for the depth curve, the throughput
  figures and the recovery pattern. Those came off one production lane on
  2026-07-28 and the per-request records are not published, so a stranger
  cannot check the table; they can only run the same ladder on their own lane.

Conditions for the measured half: depths from 1,000 to 1,048,576 tokens,
planted fact at prompt position zero, greedy decoding, one measurement per
depth unless stated.

**Not the same finding as [trap 55](55-supported-context-is-not-trained-context.md),
which is worth saying because the two share a subject.** TheTom's entry is
about *quality in the trained regime*: a rope-extended model scoring badly
against one genuinely trained long, and a GGUF export whose reduced factor
hard-caps you below the card. This entry is about *the absence of any signal*:
three ceilings that disagree, a request that is accepted and accounted for
exactly, and degradation that is not monotone in depth so a single passing
measurement tells you nothing. Read his for whether the number is meaningful,
this one for why nothing will tell you it is not.

**Symptom.** The lane advertises a million-token context. Requests at a quarter
of a million tokens return HTTP 200, with a `prompt_tokens` count that exactly
matches what you sent. Nothing is truncated, nothing is rejected, nothing is
logged. And the answer has nothing to do with the beginning of your prompt.
There is no error at any point to tell you the number in the model card stopped
being true somewhere around thirty thousand tokens.

**Three separate ceilings, and only one of them is the advertised number.**

*The advertised length* is 1,048,576, reported by the models endpoint and by
the tokenizer config's `model_max_length`.

*The trained length* is 65,536. It is in the checkpoint's own config, in plain
sight, in the rope-scaling block: a YaRN factor of 16 over an
`original_max_position_embeddings` of 65,536. Sixteen times 65,536 is exactly
the advertised million. The advertised window is not a measurement, it is an
arithmetic consequence of an extrapolation setting. Anything above 65,536 is
positions the model was never trained on.

*The served length* required an explicit override to exist at all. The
container carries `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1`. That variable exists
precisely because the engine would otherwise refuse this configuration. Someone
had to turn off a guard rail to get the number in your model card. If you did
not set that variable yourself, check whether the image did.

None of the three is the length at which the model reliably reads the start of
your prompt. That is a fourth number, and it has to be measured.

**What we measured.** Prompts of known length with a passphrase planted in the
first sentence and an explicit note that it appears only once, followed by
thousands of unique, non-repeating inventory records, then a closing decoy code
and the question. The filler is not repetition, so the answer cannot be reached
without reading the head. Greedy decoding. Every request verified: the server's
reported `prompt_tokens` matched an independent local tokenization of the same
text **exactly, at every depth, including at 1M**. Nothing is silently
truncated, and the token accounting is trustworthy. The failure is not there.

On a **cold prefill**, meaning no prefix cache reuse:

| prompt tokens | planted fact recovered | finish_reason | prefill tok/s |
|---|---|---|---|
| 1,000 | yes | stop | 492 |
| 2,000 | yes | stop | 856 |
| 4,000 | yes | stop | 680 |
| 8,000 | yes | stop | 969 |
| 16,000 | yes | stop | 875 |
| 32,000 | yes | **length** | 878 |
| 60,000 | **no** | length | 853 |
| 65,536 | yes | length | 863 |
| 70,000 | yes | length | 898 |
| 100,000 | **no** | length | 885 |
| 131,072 | **no** (2 of 2 documents) | length | 853 |
| 262,144 | **no** | length | 710 |
| 524,288 | yes | length | 531 |
| 999,996 (fully cold) | no first token inside a 1,800 s client timeout | n/a | n/a |
| 999,996 (79% cached) | **no** | length | n/a |
| 999,996 (99.99% cached) | yes, in 7 tokens | **stop** | n/a |

**It is not a cliff, and saying so would be the easy mistake.** Recovery on the
cold path is not monotonic in depth: 60,000 failed while 65,536 and 70,000
succeeded, and 524,288 succeeded after 131,072 and 262,144 had failed. Decoding
is greedy, so the variation is across documents rather than across samples of
one document. The honest description is that cold-path recovery becomes
**unreliable** from around 32,000 tokens rather than that it stops at a
particular number, and that the unreliability is what makes it dangerous: a
single passing measurement at any depth above 32,000 tells you almost nothing.
Anyone reporting a single-run needle result on a lane like this, at any depth,
is reporting a coin flip.

**The tell is finish_reason, and it changes one rung before the answers do.**
Up to 16,000 tokens the model answers the question and stops. From 32,000
onward it never emits a stop token: it gives the right passphrase and then
keeps going, generating more inventory records, until it hits the token cap. By
60,000 the answer is gone and only the record-generation remains. The model has
stopped treating the trailing question as an instruction and started treating
the whole prompt as a document to continue.

Two details confirm that reading. First, the closing decoy code was never
returned at any depth, so this is not recency bias pulling a nearby wrong
answer. Second, at 100,000 and at 262,144 the reply *began with the first
fragment of the correct passphrase* and then derailed into invented records.
The information is reaching the model. What degrades first is the instruction,
not the retrieval.

That means `finish_reason: length` is doing real work as a signal here, and it
is worth being precise about how that sits with
[trap 16](../evaluation/16-finish-reason-is-not-a-failure-signal.md), because
the careless version of this sentence is a claim form that entry exists to
retract. Trap 16's rule is **not** "cap-hits are failures" and it is not the
inverse either: it is that `finish_reason` lies in **both** directions, so you
bucket on **extractable output first** and use the finish reason only as a
diagnostic dimension. Nothing here changes that rule.

What this lane adds is that the diagnostic dimension is unusually informative
on this particular task. The correct answer is three tokens long, so
extractable output is a clean binary, and the `stop` to `length` transition
shows up a full rung of depth **before** accuracy moves. So: score the answer,
exactly as trap 16 says, and watch the finish reason as the early warning it
happens to be here. Do not promote it to the pass/fail criterion, which is the
move trap 16 records being corrected in public.

**The critical caveat, and it is large.** Every failure above is a **cold**
prefill. Re-send any of those exact prompts while the prefix cache still holds
them and they succeed: at 131,072 and at 262,144 the identical failing prompt
returns the correct passphrase in nine tokens with `finish_reason: stop`. The
usable context of this lane is therefore not one number, it is a function of
cache state. That result is its own entry, see
[trap 60](../runtime/60-cold-prefill-and-cache-hit-disagree.md), and it means a
long-context benchmark that re-runs prompts, shares a system prefix, or retries
on failure will measure a materially better lane than a cold user gets.

**Throughput, and why the advertised number is not reachable in practice.**
Cold prefill ran at roughly 850 to 970 tokens per second up to 131,072, then
fell away: 710 at 262,144 and 531 at 524,288. The rate degrades with length, so
the cost is worse than linear. A cold quarter-million-token request takes about
six minutes before the first output token; half a million takes about sixteen.

At the advertised million, a **fully cold** request did not return a first
token within a 1,800 second client timeout. The server was still working when
the client gave up: it accepted the request, held it, and released the KV
cleanly on disconnect, with the lane healthy throughout. So the first ceiling
most operators will hit is neither a model limit nor a memory limit. It is that
every default HTTP client, load balancer and reverse proxy in the path times
out first, and the failure surfaces as a client-side timeout with no
server-side error to explain it. If you advertise a million-token window, check
what your own ingress does at minute thirteen.

**A gap in this row, stated plainly rather than left to inference.** There is
**no completed fully-cold measurement at a million tokens.** The cold attempt
was abandoned when the client timed out at 1,800 seconds, and it was not
retried cold. It could not be: that abandoned attempt had already prefilled
roughly 794,000 tokens of the document before the client disconnected, and
those blocks stayed resident, so every subsequent send of that document was
partially warm by construction. Forcing a genuinely cold repeat would have
required evicting on the order of three million tokens of KV, which on a lane
with a 2,971,484-token cache means displacing effectively the entire cache with
unrelated traffic. That was not attempted on a production lane. **So the
1,048,576 cold row is an incomplete measurement, not a failure**, and the two
million-token results below are both warm to some degree.

**The advertised window is real, with one condition attached.** Re-sent after
that timeout had left most of the prompt cached, the same million-token
document was answered correctly, in seven tokens, with a clean stop, at 99.99%
cache reuse. The head of a million-token prompt is genuinely reachable on this
lane. But the intermediate run, at 79% reuse, failed exactly like a cold one.
So "1M works" and "1M does not work" are both true statements about this lane
depending on a server-side condition that appears in no request and no
response. That condition is the subject of
[trap 60](../runtime/60-cold-prefill-and-cache-hit-disagree.md), and it is the
single most important thing to know before quoting this lane's context number.

For what it is worth on the memory question: the KV cache is not the binding
constraint. The engine allocated 2,971,484 tokens of KV at NVFP4, which it
reports as 2.83x concurrency for a full-length request, so a million-token
prompt fits comfortably and was observed resident at roughly a third of the
cache. Nothing here is a capacity problem.

**The check.** Three steps, and the first two cost nothing.

1. Read the checkpoint's `config.json` rope-scaling block before you trust any
   context number. If it carries a YaRN or similar factor over an
   `original_max_position_embeddings`, the advertised window is that base times
   that factor, and the base is the trained length. Record both numbers.
2. Check whether the serving container sets a long-context override variable.
   Its presence means the advertised length did not pass the engine's own
   sanity check.
3. Measure with a fact at position zero, unique non-repeating filler, and a
   decoy at the tail, laddered across orders of magnitude. Record
   `finish_reason` alongside accuracy, and compare the server's `prompt_tokens`
   against your own tokenization at every rung. And run every rung **cold**, or
   you will measure the cache instead of the model.

**The fix.** There is no serving flag that fixes this, because nothing is
broken in the serving sense. Treat the trained length as your supported length
and the advertised length as a capability of the position encoding, not a
promise about behaviour. If you need the extrapolated range, measure your own
task at your own depths and publish the curve rather than the model card
number. And if you are chunking documents, note that this lane's honest
instruction-following limit measured an order of magnitude below its trained
length and nearly two below its advertised one.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3` serving a
community-abliterated DeepSeek-V4-Flash checkpoint (FP8 weight blocks, NVFP4
MLA KV cache, block size 256, sparse attention with a top-512 indexer,
multi-token-prediction drafter at depth 3) on two DGX Spark GB10 nodes, tensor
parallel 2, `--max-num-batched-tokens 8192`, `--max-num-seqs 4`, prefix caching
and chunked prefill both enabled. The rope-scaling arithmetic is a property of
the checkpoint. The behavioural curve is this build on this hardware, and it is
**not** a claim about stock DeepSeek V4-Flash: this is an abliterated
re-upload, and abliteration edited attention output projections across
thirty-three of the model's forty-three layers, which is not obviously
irrelevant to long-range attention. Treat the curve as scoped to this artifact
until someone runs the same ladder on the stock weights.

**Found.** 2026-07-28, first registry coverage pass on this lane.

**Attribution.** Blackwellboy. The framing "supported context is not trained
context" is a phrase we took from an external contributor's corpus; this entry
is a first-party measurement of that class on our own hardware, not a
restatement of their result. That contributor is TheTom, whose own entry on the
class landed in the same pass as
[trap 55](55-supported-context-is-not-trained-context.md), and **this entry is
the one that was renamed** when the two collided on a title, because the phrase
was his first. Related:
[trap 16](../evaluation/16-finish-reason-is-not-a-failure-signal.md),
[trap 60](../runtime/60-cold-prefill-and-cache-hit-disagree.md),
[trap 14](../versioning/14-finetune-reupload-not-drop-in.md) (why an
abliterated re-upload is its own artifact).
