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
or fabric problem. None of those are involved in the contributor's measured
case, and ordinary short smoke tests passed.

**Mechanism.** With MTP speculative decoding enabled, the drafter's
speculative tokens extend the effective sequence past `max_model_len`. The DSA
indexer's `expanded_block_table_buffer` is sized from `max_model_len` alone,
so it comes up exactly one block short: **3125 blocks allocated where 3126 are
addressed** in the contributor's reported 200K configuration.

The failure therefore needs two conditions at once: a sequence close enough to
the configured length boundary for speculative overhang to address the extra
block, and enough in-flight sequences to exercise the failing path. At lower
concurrency the contributor did not hit that address. Nothing in the resulting
error mentions speculative decoding, which is why the concurrency bisect plus
a near-boundary sequence is the discriminating check.

**Stacks and builds bitten.** A vLLM build carrying the sparse-MLA / DSA
indexer path with in-checkpoint MTP; `QuantTrio/GLM-5.2-Int4-Int8Mix`
(unpruned, 256 experts), 200K context, `fp8_ds_mla` KV, TP=4 across four DGX
Spark (GB10, sm_121a, aarch64) nodes.

Any DSA-indexer build with the same sizing defect should be exposed. The
contributor did not provide a public source/build revision for the local
3125-to-3126 patch, so this entry deliberately does **not** claim a wider
version range than the reported lane.

**The check.** Do **not** use a short 512-token smoke prompt for this trap; that
cannot exercise a block-table defect at the end of a 200K sequence. First make
a prompt whose length has been measured with the **same tokenizer** used by the
server and that leaves only a small, valid completion budget below
`max_model_len` (for example 32–64 output tokens). Record the measured prompt
token count and the server's block size. Then ramp concurrency with that exact
near-boundary request:

```bash
# PRECONDITION:
#   $NEAR_LIMIT_BODY is a JSON string containing a prompt whose tokenized
#   length was measured with the serving tokenizer and is close enough to
#   max_model_len that the requested completion reaches the final block.
#   Keep prompt_tokens + max_tokens <= max_model_len so the request itself is
#   valid; speculative overhang is the variable under test.

for c in 1 2 3 4; do
  echo "--- c=$c ---"
  pids=""
  for i in $(seq "$c"); do
    curl -sS -m300 "$ENDPOINT/v1/chat/completions" \
      -H 'Content-Type: application/json' \
      -d '{"model":"'"$MODEL"'","messages":[{"role":"user","content":'"$NEAR_LIMIT_BODY"'}],"max_tokens":64,"temperature":0}' \
      >"/tmp/minefield-120-$c-$i.json" &
    pids="$pids $!"
  done
  wait $pids || true
  curl -fsS -m5 "$ENDPOINT/v1/models" >/dev/null \
    && echo alive || { echo "DIED at c=$c"; break; }
done
```

The reported signature is clean at c=1 and c=2 and a hard engine death at
c=3, **with the near-limit sequence held constant**. A death at c=3 on a tiny
prompt is not confirmation of this mechanism; neither is gradual degradation.
Before publishing the result, record `max_model_len`, prompt token count,
`max_tokens`, block size and speculative depth so a reader can verify that the
boundary was actually reachable.

**The fix.** Size the indexer's expanded block table to include the MTP
speculative overhang — a one-line `+1` on the block count in the contributor's
serving image, reported stable since.

The robust general expression is to derive the required capacity from the
normal sequence bound plus the speculative overhang rather than from
`max_model_len` alone. The exact upstream implementation is build-specific and
is not asserted here without the contributor's source revision. Adjacent in
spirit to [11](11-speculative-depth-peak-and-collapse.md): both are cases where
a speculative-decoding parameter changes a constraint somewhere that does not
mention speculation.

**Found.** 2026-07-05, bringing up GLM-5.2 unpruned at 200K across four nodes.
Found by bisecting on concurrency after memory and fabric were ruled out.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Reported as
[#46](https://github.com/Blackwellboy/model-serving-minefield/issues/46).
