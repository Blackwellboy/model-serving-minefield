# Trap 60: a cold prefill and a prefix-cache hit do not return the same answer

**Found by Blackwellboy.**

**Status: measured here, raw not published.** 2026-07-28, on a live two-node
DeepSeek-V4-Flash lane. Four prompt lengths, ten requests, greedy decoding,
byte-identical prompts within each pair, prefix-cache hit fraction recorded per
request from the server's own metrics. The per-request records are not
published, so a stranger cannot check these pairs; what they can do is run the
two-request procedure in the check section on their own lane, which costs a
minute and settles it for that lane. This is a behavioural result on one build,
not a structural fact about a public artifact, so a runnable procedure does not
convert it to reproduced here.

**Symptom.** A long-context retrieval test fails. You re-run it to capture the
output properly and it passes. You assume you fumbled the first run, or that
the model is flaky, and you keep the second result. It was not flakiness and
the second result is not the one your users get. The first request prefilled
cold; the second was served almost entirely out of the prefix cache, and on
this lane those two paths do not produce the same answer.

The direction surprises people. The usual worry about prefix caching is that
reusing stale KV degrades quality. Here it is the reverse: **the cached path is
the one that behaves correctly, and the cold path is the one that fails.**

**The measurement.** Same document, same planted fact at prompt position zero,
same greedy settings, requests sent back to back. Cache hit fraction is
`prefix_cache_hits / prefix_cache_queries` deltas around each request.

| prompt tokens | run | cache hit | fact recovered | finish_reason | completion tokens | TTFT |
|---|---|---|---|---|---|---|
| 131,070 | 1 | 0.0% | **no** | length | 32 (capped) | 156.1 s |
| 131,070 | 2 | 99.81% | yes | stop | 8 | 1.92 s |
| 131,070 | 3 | 99.81% | yes | stop | 8 | 1.88 s |
| 131,070 | 4 | 99.81% | yes | stop | 8 | 1.87 s |
| 262,139 | 1 | 0.0% | **no** | length | 32 (capped) | 369.4 s |
| 262,139 | 2 | 99.90% | yes | stop | 9 | 2.38 s |
| 524,281 | 1 | 0.0% | yes | **length** | 32 (capped) | 986.8 s |
| 524,281 | 2 | 99.95% | yes | stop | 9 | 3.95 s |
| 999,996 | 1 | **79.44%** | **no** | length | 32 (capped) | 786.0 s |
| 999,996 | 2 | 99.99% | yes | stop | 7 | 7.52 s |

**The million-token pair is the most informative row, for two reasons.**

First, it settles what the lane can actually do: at 999,996 prompt tokens, a
fact planted in the very first sentence **is** recovered, exactly, in seven
tokens, with a clean stop. The head of a million-token prompt is genuinely
reachable on this stack. Whatever is failing on the cold path, it is not that
the information is out of range.

Second, the partial hit shows the effect is not proportional. That first run
was 79.44% cached, not cold, because a previous attempt at the same document
had timed out client-side after prefilling most of it and left those blocks
resident. Four fifths of the prompt served from cache was **not enough**: it
failed exactly like a cold run, same `finish_reason`, same drift into invented
document content. Every success in this table sits at 99.8% or above. Whatever
the mechanism is, it does not degrade gracefully with cache coverage, and a
partially warm prompt behaves like a cold one rather than like something in
between.

**The gap in that row, stated rather than implied: there is no fully-cold
million-token measurement in this table.** The 0%-cache cell at 999,996 is
missing because the cold attempt was abandoned when the client timed out at
1,800 seconds with no first token, and it could not be retried cold. The
abandoned attempt had itself cached roughly 794,000 tokens of that document,
and evicting them to force a genuine cold repeat would have meant displacing
close to the whole 2,971,484-token KV cache with unrelated traffic on a
production lane. So the million-token row contributes a 79%-versus-99.99%
contrast, which is real and informative, but **not** a cold-versus-warm one.
The cold-versus-warm claim rests on the 131,070, 262,139 and 524,281 pairs,
where the cold arm is a measured 0.0% hit.

That failing run also shows the clearest instance of the partial-retrieval
signature: the planted passphrase was `quiet-foundry-3946` and the reply opened
`quiet-ledge-1234` before continuing into fabricated inventory records. The
first word is right. The rest is invented. The model is reaching the head of
the prompt and then losing it mid-token-sequence, which is not the shape of a
context window that has run out.

Read the table in two parts, because the two claims have different strength.

**The behavioural difference is 3 of 3.** In every pair, the cold run never
emitted a stop token and ran to the cap producing invented document content;
the warm run answered in eight or nine tokens and stopped cleanly. Even at
524,281, where the cold run did surface the right passphrase, it then kept
generating rather than stopping.

**The correctness difference is 2 of 3.** At 131,070 and 262,139 the cold run
did not produce the planted fact at all and the warm run did.

**Is it just run-to-run noise? No, but the honest argument is not the obvious
one, and this is the part a reader should not skim.**

Runs 2, 3 and 4 at 131,070 are byte-identical to each other, and decoding is
greedy with temperature pinned to zero. **That alone would be a weak argument**,
and we are not making it, because this lane is **not** fully deterministic at
temperature zero.

> **Measured (first-party, n=6 per prompt):** in a separate 30-request sweep at
> short context, prose, JSON and tool-calling prompts reproduced byte-identically
> across six repeats each, while a code prompt produced four distinct outputs in
> six runs (completion lengths 114, 107, 114, 157, 160, 160), and a maths
> prompt hit the 256-token cap in five of six runs and stopped cleanly at 244
> in the sixth. Same prompt, same greedy settings, same lane. The code prompt
> is the strong case; the maths prompt shows two distinct completion lengths,
> not four, and is reported that way rather than folded in as a second
> equivalent instance.
>
> **Hypothesis, not established:** the most likely cause is the probabilistic
> draft sampling the speculative decoder is configured with. **This was not
> isolated.** Isolating it means changing the drafter configuration, which is a
> serve change the production lane does not permit. Nobody has demonstrated the
> cause, and no other candidate was excluded.

So temperature-zero reproducibility on this lane is **task-dependent, and that
is a measured fact with an unproven mechanism**. The practical consequence for
this entry is direct: **a single cold/warm pair proves nothing here**, and any
n=1 result on this lane should be treated the same way. The claim below rests
on the four-versus-six `finish_reason` separation set out in the table, not on
any individual pair, precisely because the per-pair noise floor is non-zero and
we cannot currently explain it. An earlier draft of this sentence cited a
ten-versus-ten separation; that aggregation was retracted further down this
page and this sentence should have been corrected with it.

What carries the claim is the consistency of the direction across every run at
depth where the cache-hit fraction was actually recorded. **Ten requests carry
per-request prefix-cache counters: four at 79.44% coverage or below, all four
with `finish_reason: length`; six at 99.81% or above, all six with
`finish_reason: stop` and a short exact answer.** Four documents, four prompt
lengths, no overlap between the groups. Noise does not sort itself by cache-hit
fraction.

**Two things are deliberately kept out of that count, and the second one cuts
against this entry.**

*Supporting but not counted:* the cold depth ladder that opened the session ran
six further documents at 31,999, 59,994, 65,531, 69,994, 99,993 and 131,068
tokens and returned `finish_reason: length` on all six. Those requests were
cold by time to first token (prefill at 853 to 969 tok/s, against a warm TTFT
that never exceeded 8 s anywhere in the session) rather than by counter,
because that harness did not scrape the prefix-cache metrics. They agree with
the direction and they are stated separately rather than pooled into the ten.

*The counterexample:* **one cold run at 131,068 tokens finished `stop`, with
the exact planted fact, in 11 completion tokens.** It is arm C of the framing
control, which places the question **before** the document. That moves the
divergence point to token zero, so the run prefilled cold (157.07 s TTFT,
against 1.43 to 1.77 s for arms A, B and D of the same control, which share the
cached document head). It is not a member of the cache contrast, because its
prompt order differs from every other run in this entry and cache state is
therefore not the only thing that changed. It is recorded here anyway, in the
entry it complicates, because it is the **only clean stop on a cold path
anywhere in this session** and it constrains the mechanism: the cold path can
reach the head of a 131k prompt and terminate correctly when the instruction
precedes the document. Whatever is failing is better described as losing the
instruction than as failing to reach the fact.

An earlier draft of this entry pooled the ladder and the framing control into
the measured set and reported a ten-versus-ten split. That aggregation was
wrong in two ways: it treated six ladder runs and four framing runs as having
cache fractions that were never measured, and it placed arm C in the high-cache
arm when its own TTFT says it prefilled cold. The corrected counts are above:
**four low-cache runs, all `finish_reason: length`, against six high-cache runs,
all `stop`**. The direction of the finding is unchanged; its n is smaller and it
now carries a counterexample.

**If you are searching for the retracted figure**, the phrasings to look for are
"10-versus-10", "ten-versus-ten" and "10 versus 10", and they should appear
nowhere in this repository except in this paragraph and in the do-not-cite
register. The claim they encoded, that the separation was ten against ten with
no exceptions, is retracted: cold recovery of the planted fact was **1 of 4**,
not a clean sweep, and 524,281 is an explicit counterexample where the cold run
did surface the passphrase.

**Mechanism, offered as a hypothesis and explicitly not established here.** The
two paths compute the same KV by different routes. A cold prefill of 262,139
tokens runs as thirty-two chunked-prefill passes of 8,192 tokens; a 99.9% cache
hit replays stored KV blocks and computes only the last partial block. Those
are different kernel shapes over a quantised KV cache, so they are not
bit-identical, and this model's attention is sparse: an indexer selects a
top-512 set of tokens per query. Small numeric differences do not have to stay
small when they feed a selection. If the head of the prompt falls out of the
selected set on one path and stays in on the other, you get exactly this
result: the information is present in both, and only one path looks at it.

Consistent with that story, and worth recording as the boundary of what we
know: prompts small enough to prefill in one or two chunks recovered the fact
cleanly and stopped normally on the cold path. The divergence appears only at
many-chunk depths. We did **not** test the decisive experiment, which is the
same ladder with chunked prefill disabled, because that requires restarting a
production lane. Until someone runs it, chunking is a hypothesis, not the
cause.

**The experiment is specified rather than left as a wish.**
[The chunked-prefill versus cache-replay specification](../../mining/2026-07-28-chunked-prefill-vs-cache-replay-experiment.md)
gives the exact flags, a paired 2x2x2 over prefill shape, KV dtype and cache
state, n and its justification, pre-registered endpoints, and a decision table
that includes **what result would make this entry's mechanism paragraph wrong**.
It also notes that this sits on the same axis as the proposed registry entry
about KV-quant quality numbers never reading the quantised cache: if a
single-pass prefill can leave a quantised cache written but not read back, then
read-back is precisely what separates our cold path from our warm path, and the
two mechanisms are one mechanism seen from opposite sides.

**Why this matters more than a latency footnote.** Almost every way people
measure long context reuses prefixes.

- A benchmark harness that retries a failed request scores the retry, which is
  a different code path.
- A suite that shares one long system prompt or one document across many
  questions pays cold once and measures warm for everything after.
- A/B comparisons run back to back give the second arm a warm cache and the
  first a cold one, which is a confound in the shape of
  [trap 17](../evaluation/17-per-arm-recommended-sampling-confound.md) but
  hiding in server state rather than in request parameters.
- Interactive testing is warm almost by definition, because you are re-sending
  variations of the same long prompt. Production traffic from many users on
  distinct documents is cold almost by definition. So the lane looks good in
  every session where a human is watching it.

**The check.** Send one long prompt with a fact at position zero. Record the
answer, the `finish_reason` and the cache-hit delta from the server's metrics.
Send the byte-identical prompt again immediately and record the same three. If
the cache-hit fraction goes from roughly zero to roughly one and either the
answer or the finish reason changes, you have this. Two requests, no
configuration change, and it works on any server that exposes prefix-cache
counters.

To measure a lane honestly afterwards, make every evaluation prompt unique at
the **front**, not just the back. A per-item nonce in the first tokens defeats
prefix reuse; varying only the trailing question does not, because the shared
head is what gets cached.

**Do not rely on the disable flag alone.** On llama.cpp, @Defilan set
`cache_prompt: false` on every request and the warm arm still diverged from the
cold arm, so a flag that reads as "prefix reuse off" is not a demonstration
that nothing carried over. Flush the slot between samples with an unrelated
prompt and prove the flush works on your own lane with a cold control, then
report **both** the flag and the flush procedure in the protocol. Report the
concurrency setting alongside them: @apollo-mg measured a separate channel in
which batching two sequences together changes the reduction order and moves the
output at temperature zero, which `-np 1` suppresses.

**The fix.** There is no flag that makes the two paths agree, and disabling
prefix caching would trade a large latency win for the worse of the two
behaviours. The actionable part is measurement discipline: report cold and warm
as separate numbers rather than averaging them, state which one your benchmark
measured, and treat a long-context result that was not verified cold as an
upper bound rather than a result.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3` serving a
community-abliterated DeepSeek-V4-Flash checkpoint on two DGX Spark GB10 nodes,
tensor parallel 2, NVFP4 MLA KV cache at block size 256, sparse attention with
a top-512 indexer, `--max-num-batched-tokens 8192`, `--max-num-seqs 4`, prefix
caching and chunked prefill both enabled, multi-token-prediction drafter at
depth 3. Scope this to that combination. The ingredients we think are load
bearing, sparse top-k attention plus a quantised KV cache plus multi-chunk
prefill, are individually common and jointly not, and this is not a claim about
stock DeepSeek V4-Flash or about prefix caching in general.

**Independent convergence, three stacks, reported separately rather than
pooled.** Within about twenty-four hours, three lines of evidence arrived at
cache state deciding an outcome that the request alone should have decided.
They are listed with their own conditions and attributed by handle. Only the
third is first-party. **The numbers are not combined and no pooled figure is
computed**, because the three measure different endpoints on different
runtimes and the failure modes differ in kind.

| line | who | stack | what was measured | result |
|---|---|---|---|---|
| 1 | @apollo-mg, **contributor-reported** | llama.cpp, upstream `ggml-org/llama.cpp` at `0e4a03622` | output byte-hash, identical request | prefix reuse is on by default (`common/common.h:622`, `cache_prompt = true`); a fresh 4,704-token prefill returns one hash and repeats it, a warm 30-token prefix returns a different hash. Stock flags, no concurrency, no restart. |
| 2 | @Defilan, **contributor-reported** | llama.cpp Vulkan on gfx1151, Laguna S 2.1, single slot, temp 0, `cache_prompt: false` set explicitly | output byte-hash, n=3 per arm | cold arm deterministic across three runs; warm arm diverges on two of three and falls back to the cold hash on the third. Stated by its author as an existence proof and not a rate, with the mechanism explicitly not identified. |
| 3 | this entry, first-party | vLLM `0.21.1rc1.dev339+g1967a5627bc3`, DeepSeek-V4-Flash NVFP4, TP=2, two GB10 nodes | `finish_reason` and fact recovery, per-request cache-hit counters | four low-cache runs all `length`, six high-cache runs all `stop`; see the table above. |

**What the three do and do not share.** Lines 1 and 2 are llama.cpp family and
line 3 is vLLM, so this is not a property of one serving layer. All three show
server state deciding an outcome the request did not. **They differ in kind at
the point that matters most**: lines 1 and 2 measured **bytes**, where the
mechanism offered is a near-tie flipping under a changed reduction order, and
@Defilan states plainly that whether that can move a *behavioural* verdict
rather than exact tokens is a check he has not run. Line 3 is a behavioural
verdict: `stop` versus `length` is not a near-tie, and the model stops
answering the question and continues the document. So line 3 answers that open
question in the affirmative **for the class**, and is not evidence about either
of the other two runs.

Line 2 additionally establishes something no amount of first-party work here
could: **setting the flag is not the same as isolating the request.**
@Defilan set `cache_prompt: false` on every request and still saw the warm arm
diverge. The practical consequence is in the check below.

This also converges with **trap 55** in the fifteen-entry contribution from
@TheTom (run order and warm-cache artifacts producing a prefill win that
reproduced on a branch without the feature). That is a fourth stack and a
performance endpoint rather than a correctness one.

**Found.** 2026-07-28, during a context-depth ladder, when a prompt that had
failed cold ten minutes earlier passed on re-send.

**Attribution.** Blackwellboy. Related:
[trap 61](../evaluation/61-advertised-window-fails-silently.md) (the
depth curve this was found inside),
[trap 25](../template/25-empty-think-blocks-poison-prefix-cache.md) (prefix
caching as a correctness surface rather than a performance one),
[trap 17](../evaluation/17-per-arm-recommended-sampling-confound.md).
