# Experiment specification: is chunked prefill what makes a cold long prompt answer differently?

**Status: NOT RUN. Specification only.** Written 2026-07-28 alongside the
DeepSeek-V4-Flash coverage entries. This experiment requires a **serve change**
and must never be run on the production lane, which is request-level only and
does not go down. It is written to be executable by someone else, later, on a
scratch serve.

## What this is for

The staged entry
[cold prefill and cache hit disagree](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md)
establishes a measured fact and offers an unproven mechanism. The fact: on a
live DeepSeek-V4-Flash lane, byte-identical long prompts answer differently
depending on prefix-cache state, with a perfect 10-versus-10 separation on
`finish_reason` across six prompt lengths from 32,000 to 999,996 tokens. Ten
runs at 79% cache coverage or below all ran to the token cap emitting invented
document content; ten runs at 99.8% or above all stopped cleanly with a short
exact answer.

The offered mechanism is that the two paths compute the same KV by different
routes. A cold prefill of a long prompt runs as many chunked passes of
`max_num_batched_tokens`; a near-total cache hit replays stored KV blocks and
computes only the final partial block. Those are different kernel shapes over
an NVFP4-quantised KV cache feeding a sparse attention indexer that selects a
top-512 token set per query. A small numeric difference does not have to stay
small once it feeds a selection.

**That is a hypothesis with no experiment behind it.** This document is the
experiment.

## Why it is on the same axis as two other open items

Cross-reference all three when this runs; they are one question asked three
ways.

**Proposed registry entry 56, "your KV-quant quality numbers never read the
quantized cache"** (external contributor, currently classified HOLD pending
the with/without pair). Its claim is that a default single-pass prefill can
leave a quantised KV cache **written but never read back** inside the measured
window, so a quality number taken that way is not a KV-quant result at all. Its
proposed detection protocol is the same two-run shape used below: same build,
same checkpoint, only `max_num_batched_tokens` changed. If that claim is
right, then read-back is exactly what distinguishes our cold path from our warm
path, and entry 56's mechanism and ours are the same mechanism seen from
opposite sides: theirs says the quantised cache is not read enough, ours says
what you get depends on how it was written and re-read.

**Our own queued action item on our published NVFP4-KV numbers.** Recorded
during the intake assessment of that PR: if a single-pass prefill can leave a
quantised KV cache written but never read back inside the measured window, our
own NVFP4-KV numbers may carry the same defect, because **they were not
measured with chunked prefill forced**. That item is ours to run regardless of
whether the external entry lands. Phase 2 below is that check, and running it
here means it is answered on the same hardware and in the same session as the
mechanism question rather than separately.

**Proposed registry entry 57 shares a title with one of our staged entries.**
Ours is
[the advertised window fails silently](../traps/evaluation/61-advertised-window-fails-silently.md).
Theirs, per the intake dedupe pass, is the trained-regime-quality and GGUF
metadata-capping side and was assessed as distinct material. The two are not
duplicates, but they cannot both land under the same name. **Reconcile the
titles at land time**, and credit the phrase to the contributor's corpus, which
is where we took it from; our entry already says so in its attribution.

## Hard prerequisite, stated first because it is the blocker

This needs a **scratch serve of the same checkpoint and image**, not the
production lane. That is not currently available and is the reason this is a
specification rather than a result:

- The weights are 156 GiB per node and the model requires tensor parallel 2
  across two nodes. It does not fit one node.
- The production pair has roughly 7 to 9 GiB free per node while the live lane
  is resident, so a scratch serve cannot run beside it.
- A prior session established that the only realistic routes are an approved
  maintenance window on the production lane with a restore recipe banked, or a
  second node pair with the weights copied over. Both need explicit owner
  authorisation.

**Do not attempt to satisfy this by reconfiguring the production lane.** If the
only available route is a maintenance window, the rollback anchor container
must be verified present first and the full launch recipe banked, exactly as
the 2026-07-22 and 2026-07-28 recovery records describe.

If a scratch serve is genuinely unavailable, a **reduced but still useful**
variant is noted at the end.

## Design

A paired 2 x 2 x 2. The three factors are prefill shape, KV cache dtype, and
cache state.

### Fixed across every arm

| | |
|---|---|
| Checkpoint | the same community-abliterated DeepSeek-V4-Flash used in production |
| Image | `vllm-dspark-runtime:dspark-nvfp4-stage-c`, same digest on both nodes |
| Parallelism | tensor parallel 2, two nodes, as production |
| Depth | **65,536 tokens** per prompt (see "why 65,536" below) |
| `--max-model-len` | 131072 (headroom above the probe depth, low enough to allow a single-pass arm) |
| `--max-num-seqs` | 4, as production |
| Speculative config | K=3, `draft_sample_method` probabilistic, as production |
| Sampling | greedy, temperature 0.0, top_p 1.0, `max_tokens` 32 |
| Prompt construction | identical generator to the staged work: planted passphrase in the first sentence, unique non-repeating inventory filler, decoy code at the tail, question last |

### The three factors

**Factor A, prefill shape.**

- `A_chunked`: `--max-num-batched-tokens 8192` and chunked prefill enabled.
  This is the production setting and gives 8 prefill passes at 65,536.
- `A_single`: `--max-num-batched-tokens 131072` with chunked prefill disabled,
  so the prompt prefills in one pass. On this engine, disabling chunked prefill
  requires `max_num_batched_tokens` to be at least `max_model_len`, which is
  why `--max-model-len` is pinned to 131072 rather than left at 1048576.
  **Record the engine's own startup line confirming chunked prefill is off**;
  do not assume the flag took, which is a failure mode with its own registry
  entry.

**Factor B, KV cache dtype.**

- `B_nvfp4`: `--kv-cache-dtype nvfp4_ds_mla --block-size 256`, production.
- `B_unquant`: `--kv-cache-dtype auto` (bf16), block size left at the engine
  default for that dtype. Expect a much smaller KV cache; at 65,536 tokens and
  `max-num-seqs` 4 this must still fit, and the allocated token count must be
  recorded from the engine log to prove it did.

**Factor C, cache state.** Not a serve flag, a request protocol.

- `C_cold`: `--no-enable-prefix-caching`. Every request computes from scratch.
  Turning it off rather than relying on unique documents removes any doubt
  about partial block reuse.
- `C_warm`: prefix caching enabled; each document is sent **twice** back to
  back, and only the **second** send is scored. The first send is the warmer
  and is discarded, though its result should still be logged.

Factor C requires a restart to toggle, so run all cold cells for a given (A, B)
build, then restart into the warm build. Four builds total, two sends per
document in the warm builds.

### Documents and pairing

Generate **20 documents** at 65,536 tokens with fixed seeds `sc-001` to
`sc-020`, and use **the same 20 documents in every cell**. This is a paired
design: cell differences must not be document luck. Record each document's
planted passphrase, decoy, and local token count.

Cell count: 8 cells (2 x 2 x 2) x 20 documents = 160 scored requests, plus 40
discarded warmer sends in each warm build.

### Why 65,536

Three reasons, and the choice matters.

1. It is the checkpoint's **trained** context, the YaRN base. Staying at or
   below it removes extrapolation as a competing explanation for any failure.
2. It is deep enough to be in the regime where the production effect appears:
   the cold ladder showed the `finish_reason` flip from 32,000 onward and a
   cold failure at 60,000.
3. Single-pass prefill at 65,536 is plausible on this hardware, where at
   262,144 or above it is not. The experiment must be runnable.

A depth this shallow means the effect may be **weaker** here than at 262,144.
That is a real limitation and is handled in the decision table: a null result
at 65,536 does not clear the mechanism at greater depth, it only fails to
support it at this depth.

## Endpoints, pre-registered before any data is collected

**Primary: `finish_reason` is `stop`.** This is the endpoint with the perfect
separation in the production observation, 10 versus 10, and it flips one rung
of depth before accuracy does. Scored per request as a binary.

**Secondary: planted passphrase recovered.** Case-insensitive substring match
of the exact passphrase in the completion. Noisier, because production cold
recovery ran about 4 successes in 10.

**Tertiary, recorded but not tested:** the partial-retrieval signature, meaning
a completion that opens with the first word of the passphrase and then diverges
(observed at 100,000, 262,144 and 999,996 in production). Also record TTFT,
total latency, prompt tokens as the server reports them against an independent
local tokenisation, prefix-cache hit fraction per request, and the spec-decode
counters.

**Analysis.** McNemar on the paired binaries for each factor contrast, since
documents are shared across cells. Report the raw 2x2 tables, not just p
values.

## Why n = 20 per cell

The primary endpoint is close to deterministic in the production data: cold and
warm did not overlap at all across 20 requests. If that holds, n=10 per cell
would settle it and n=20 is comfortable. The secondary endpoint is the one that
sets the number: distinguishing roughly 40% recovery from roughly 90% at 80%
power and alpha 0.05 needs about 20 per arm in a paired design. Twenty serves
both.

If the primary endpoint shows a clean separation in the first 10 documents of a
cell, that is worth logging but is **not** grounds to stop the cell early;
finish the 20 so the paired analysis stays balanced.

## Decision table

Let "divergence" mean cold and warm disagree on the primary endpoint within a
given (A, B) build.

| Result | Reading |
|---|---|
| Divergence in `A_chunked`, **absent** in `A_single` | **Hypothesis supported.** Multi-pass prefill is the operative difference. This is the outcome the staged entry predicts. |
| Divergence present in **both** `A_chunked` and `A_single` | **Hypothesis refuted as stated.** Chunking is not the cause. The difference is between replaying stored KV and computing it, whatever the pass count, which points at the cache replay path itself or at the sparse indexer's state, not at chunking. The entry's mechanism paragraph must be rewritten. |
| Divergence in `B_nvfp4`, **absent** in `B_unquant` | **KV quantisation is implicated**, independently of chunking. This is the result that speaks directly to proposed entry 56 and settles our own queued NVFP4 item: it would mean our published NVFP4-KV numbers need re-measuring under forced chunked prefill. |
| Divergence absent in `B_unquant` **and** absent in `A_single` | Both factors matter and likely interact. Report the interaction term; do not attribute to one. |
| **No divergence anywhere**, warm and cold agree in all four builds | **The scratch serve does not reproduce the production observation.** Do not read this as clearing the production lane. It means the effect depends on something held constant here and varied there: depth (65,536 versus 262,144 and above), `max-model-len` (131072 versus 1048576, which changes the YaRN regime), or the production lane's specific state. Escalate to a depth arm before concluding anything. |
| Divergence in **every** cell including `B_unquant` and `A_single` | Neither quantisation nor chunking. Next suspects, in order: the sparse indexer's top-512 selection being recomputed rather than restored; the MTP drafter's interaction with a resumed sequence; and non-determinism unrelated to cache state, which the control below is there to bound. |

## Controls that must run alongside

**Determinism floor.** In every build, send 5 of the documents twice under
identical cache conditions (both cold, or both warm) and record whether the
completions are byte-identical. The staged work measured task-dependent
non-determinism at temperature 0 on short prompts: prose, JSON and tool prompts
reproduced 6 out of 6, while code and maths did not. **Any divergence rate
measured across cells must be interpreted against this floor.** If the
same-condition repeat rate is itself high, the primary endpoint is not clean
and the whole design needs re-thinking before its numbers are quoted.

**Flag verification, not flag intent.** For each of the four builds, capture
the engine's own startup configuration line and confirm: chunked prefill state,
`max_num_batched_tokens`, `kv_cache_dtype`, allocated KV cache token count,
prefix caching state, and the speculative config. A build that silently did not
take the flag would produce a false null in the most convincing direction.

**Token accounting.** Confirm the server's `prompt_tokens` matches an
independent local tokenisation for every request, as it did at every depth in
the production work. A mismatch appearing only in one arm would be its own
finding and would invalidate that arm's comparison.

## Cost

At 65,536 tokens and roughly 860 tokens per second of cold prefill, a cold
scored request is about 80 seconds; warm sends are a few seconds. Estimate:

- Cold builds: 2 builds x 20 documents x ~80 s, about 55 minutes of prefill.
- Warm builds: 2 builds x 20 documents x (one ~80 s warmer plus one fast
  scored send), about 60 minutes.
- Plus 4 model loads. Loading this checkpoint took about 9.5 minutes in the
  recorded recovery, so roughly 40 minutes of loading.
- Plus the determinism control, about 15 minutes.

**Roughly 3 hours of occupancy**, dominated by prefill and model loads, not by
decode. Comfortably an overnight run on a scratch pair.

## Reduced variant if no scratch serve is ever authorised

Two factors of the three can be tested at **request level only**, on any lane,
because cache state is a request protocol rather than a flag. That gives the
cold-versus-warm contrast at higher n and more depths, and it is worth doing:
it would turn the 10-versus-10 separation into a properly powered estimate.

It **cannot** test the mechanism. Prefill shape and KV dtype are both serve
flags. So the reduced variant strengthens the entry's *fact* and leaves its
*mechanism* exactly as unproven as it is today. If that is the only route
available, say so in the entry rather than letting a bigger n read as if the
mechanism had been settled.

## What must not happen

Running any part of this against the production lane. Toggling prefix caching,
chunked prefill or KV dtype there is a serve change on a lane documented as
never going down, and the cold-path behaviour under investigation is not a
fault requiring urgent diagnosis: it is a characterised property with a
published workaround, which is to verify long-context results cold and to make
evaluation prompts unique at the front.
