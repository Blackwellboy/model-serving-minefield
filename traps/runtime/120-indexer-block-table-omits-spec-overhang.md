# Trap 120: stable at two concurrent, dead at three, with no memory or fabric involvement

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (deterministic by
concurrency level; the one-line fix has held in production since).

**Symptom.** The server is completely stable single-stream and at two
concurrent requests. At **three or more**, the engine dies. Concurrency is the
only variable: same prompts, same lengths, same model, same everything else.
There is no degradation curve beforehand — it works, works, works, then the
engine is gone.

Because it appears only under load, it reads as a memory-pressure, scheduler
or fabric problem. None of those are involved, and every smoke test passes.

**Mechanism.** With MTP speculative decoding enabled, the drafter's
speculative tokens extend the effective sequence past `max_model_len`. The DSA
indexer's `expanded_block_table_buffer` is sized from `max_model_len` alone,
so it comes up exactly one block short: **3125 blocks allocated where 3126 are
addressed**.

At low concurrency the final block is never reached. Once enough sequences are
in flight to exercise the boundary, the write lands outside the buffer and
takes the engine with it. Nothing in the resulting error mentions speculative
decoding, which is why the concurrency bisect is the fastest route to it.

**Stacks and builds bitten.** A vLLM build carrying the sparse-MLA / DSA
indexer path with in-checkpoint MTP; `QuantTrio/GLM-5.2-Int4-Int8Mix`
(unpruned, 256 experts), 200K context, `fp8_ds_mla` KV, TP=4 across four DGX
Spark (GB10, sm_121a, aarch64) nodes.

Any DSA-indexer build that sizes the block table without accounting for
spec-token overhang should be exposed. The trigger is MTP plus enough
concurrency to reach the boundary, not anything Spark-specific.

**The check.** Ramp concurrency and look for a hard edge rather than a curve:

```bash
for c in 1 2 3 4; do
  echo "--- c=$c ---"
  for i in $(seq $c); do
    curl -s -m120 "$ENDPOINT/v1/chat/completions" \
      -H 'Content-Type: application/json' \
      -d '{"model":"'"$MODEL"'","messages":[{"role":"user",
           "content":"Write 400 words on photosynthesis."}],
           "max_tokens":512,"temperature":0}' >/dev/null &
  done; wait
  curl -s -m5 "$ENDPOINT/v1/models" >/dev/null \
    && echo alive || { echo "DIED at c=$c"; break; }
done
```

Clean at c=1 and c=2 and dead at c=3, reproducibly, is the signature. If the
same ramp degrades gradually instead, you are looking at something else.

**The fix.** Size the indexer's expanded block table to include the MTP
speculative overhang — a one-line `+1` on the block count, patched into our
serving image and stable since.

The correct general fix is deriving the buffer from
`max_model_len + num_speculative_tokens` rather than `max_model_len`, so the
relationship is expressed rather than rediscovered. Adjacent in spirit to
[11](11-speculative-depth-peak-and-collapse.md): both are cases where a
speculative-decoding parameter silently changes a constraint somewhere that
does not mention speculation.

**Found.** 2026-07-05, bringing up GLM-5.2 unpruned at 200K across four nodes.
Found by bisecting on concurrency after memory and fabric were ruled out.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Reported as
[#46](https://github.com/Blackwellboy/model-serving-minefield/issues/46).
