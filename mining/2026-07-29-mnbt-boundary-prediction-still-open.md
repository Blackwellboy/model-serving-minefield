# Open prediction: does the cold-prefill failure boundary track `--max-num-batched-tokens`?

**Status: PUBLISHED AND UNTESTED. Still open.** Written 2026-07-29 so that
whoever runs the next screen inherits the framing rather than rebuilding it.

## The prediction, unchanged

[Trap 60 / the cold-prefill entry](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md)
and its successor establish, on a live two-node DeepSeek-V4-Flash lane running
`--max-num-batched-tokens 8192`:

- cold prompts of **1 or 2 prefill chunks: 14 of 14 clean**
- cold prompts of **3 or more chunks: 1 of 21 clean**
- the last clean pass at **16,302** tokens and the first failure at **16,447**,
  a 145-token bracket containing **2 x 8192 = 16,384**
- warm arms unaffected (13/14 clean), so **a cache hit is a pass** and any
  fixed-order harness will miss this entirely

The entry states the causation honestly as a strong coincidence, not a proof,
and makes the sharp prediction: **set `--max-num-batched-tokens` to 4096 and the
boundary should move to 8192.** If it does not move, the entry is wrong about
the mechanism and right only about the symptom, and says so itself.

**That prediction has not been tested. It remains published and open.**

## Why it could not be tested on DeepSeek-V4-Flash

Testing it requires restarting the serve with a different flag value. The lane
carrying that checkpoint is a production lane that does not go down, and the
weights live only on that pair of nodes by deliberate policy. A plan to copy
them elsewhere was raised and **ruled against** - the weights are on that pair
*because* that pair is the lane, and that is correct rather than an obstacle to
route around.

So the model that exhibits the boundary cannot be restarted. That is the whole
difficulty, and it is not going to be engineered away.

## What the cross-model attempt found

Run 2026-07-28 on **Laguna S 2.1 NVFP4** (poolside, 67 GiB, vLLM 0.25.1,
`dflash` K=7, fp8 KV, FLASHINFER, block size 16, `--max-model-len 262144`,
`--max-num-seqs 4`, prefix caching and chunked prefill both on) on a single
GB10 node, scratch serve, torn down afterwards.

Same prompt construction as the original: code planted at the top, long record
manifest, question last, token-exact via the server's own tokenizer. **Cold was
measured, not assumed** - prefix-cache hit fraction read around every request;
every cold arm below reported exactly 0.0000, and no request landed in the
excluded intermediate band.

| MNBT | prompt tokens | chunks | cold arms | result |
|---|---|---|---|---|
| 8192 | 19,965 | 3 | 1 | clean, `stop` |
| 8192 | 39,973 | 5 | 2 | clean, `stop` |
| 8192 | 69,984 | 9 | 2 | clean, `stop` |
| 8192 | 139,952 | 18 | 2 | clean, `stop` |
| 4096 | 19,965 | 5 | 2 | clean, `stop` |
| 4096 | 69,984 | 18 | 2 | clean, `stop` |
| 4096 | 139,952 | 35 | 2 | clean, `stop` |

**13 of 13 cold arms clean, up to 35 chunks, at both flag values.** DeepSeek-V4
is 1 of 21 at 3 or more chunks.

**The positive control, which is what makes that null worth anything.** The same
harness, same prompt, same depth, pointed at the DeepSeek lane reproduced the
failure: cold returned `finish_reason: length`, emitted the code and then
**invented a question and answered it**, running to the cap, with an orphaned
`</think>` leaked into `content`. Warm on the identical prompt answered in 8
tokens and stopped. So the instrument detects the failure where it exists and
reports clean where it does not, on the same day.

## What this does and does not do to the prediction

**It bounds the claim. It does not refute it.**

- The symptom is **not** a general property of vLLM chunked prefill. Two serves
  with chunked prefill and prefix caching both enabled behave completely
  differently. Anyone reading the original entry as "chunked prefill drops your
  last turn" is over-generalising, and this is the evidence against that reading.
- The `2 x MNBT` prediction is **still untested**, because you cannot watch a
  boundary move on a model that has none. A null on Laguna is not a null on the
  prediction.
- The correct scope is "does not reproduce on **this build**", not "is caused by
  the DeepSeek weights". Laguna differs in more than the checkpoint: `dflash`
  K=7 vs `dspark` K=3, fp8 vs `nvfp4_ds_mla` KV, FLASHINFER attention, block
  size 16 vs 256, 262k vs 1M max length. Any of those could carry the effect.

## What the next screen needs

The prediction needs a model that **exhibits the boundary** on a serve that
**can be restarted**. DeepSeek exhibits it and cannot be restarted; Laguna can
be restarted and does not exhibit it. Find the third case.

**Screen candidates cheaply - two requests decide it:**

1. build a prompt of ~20,000 tokens, a fact planted early, a question at the end
2. fire it cold, record `finish_reason` and whether it answered
3. fire the identical request again (now warm), record the same

If the first continues the document or invents a question and the second answers
cleanly, that model exhibits the boundary and is worth the full ladder. If both
answer, move on - that is 90 seconds spent, not an afternoon.

**Next candidate: Nemotron 3 Nano 30B A3B NVFP4** (`NemotronHForCausalLM`,
Mamba-Transformer hybrid, 19 GB, 262k context). It is the most architecturally
distant candidate available *and* it is restartable, which is the combination
Laguna lacked. Two cautions carried forward: it needs a serving venv built on
the node first, and Mamba SSM state sits outside `mem-fraction-static`, so the
launch must be bounded - an unbounded NVFP4 launch swap-killed that node once
already.

**If it exhibits the boundary, run the pre-registered design:** three flag
levels (4096 / 8192 / 16384) in **A-B-C-A order** so the repeated 8192 arm
separates a real flag effect from a restart artifact; cold arms only, cold
verified per request from the cache counters; intermediate hit fractions
excluded and counted; token-exact ladders bracketing each predicted boundary;
and the refutation criterion fixed in advance - **if the bracket sits near
16,384 regardless of the flag, the prediction is refuted and publishes with
equal weight.**

**Attribution.** Blackwellboy.
