# Trap 98: speculative-decode max_seqs default crashes on unified memory

**Found by Nemo (@NemoSMF).**

**Status: contributor-measured, conditions as reported** (12-hour soak on
DGX Spark GB10, 128 GB UMA; raw published in the
[NemoKnowledgebase](https://github.com/smfworks/NemoKnowledgebase/benchmarks/laguna-s-2.1-nvfp4/)).

**Symptom.** vLLM launches a model with DFlash speculative decoding using the
card-recommended `--max-num-seqs` value (32 or the default 256), loads weights
successfully, and crashes during KV cache allocation or on the first concurrent
request. The error reads as an OOM, and the natural response is to lower the
utilization fraction — but the real variable is `max-num-seqs`, which the model
card and the server default set far higher than unified memory can sustain under
speculative decoding.

**Mechanism.** DFlash speculative decoding reserves per-sequence state for each
speculative slot (15 tokens in this case), and `--max-num-seqs` multiplies that
across all concurrent sequences. On a discrete GPU with abundant VRAM, the
default of 256 is conservative. On 128 GB unified memory, where the KV pool, the
OS, the tokenizer process, and the model weights all share one physical RAM
pool, the default exhausts memory before the first request lands. The model
card's recommended value of 32 was tested on discrete VRAM and does not account
for the unified-memory tax.

**Stacks and builds bitten.** vLLM 0.25.1, `poolside/Laguna-S-2.1-NVFP4`
revision `b482b5d57fda6e4e562a652869bde24ba2a57c92`, DFlash with 15 speculative
tokens, DGX Spark GB10 128 GB UMA. The default `max-num-seqs=256` crashed at
startup. The card-recommended `max-num-seqs=32` also crashed under concurrent
load. `max-num-seqs=4` was soak-tested stable: 389 sessions, 2,947 turns, 0
crashes, 0 restarts, 4 GiB memory creep over 12 hours. GPU memory utilization
was 0.82.

**The check.** Before serving with speculative decoding on unified memory:

```bash
# Check what max-num-seqs your launch uses
grep -oP 'max-num-seqs\s+\K\d+' <your-launch-script>
# If it's >4 on 128 GB UMA with DFlash, you are likely overprovisioned

# After startup, verify the server is actually serving, not just loaded:
curl -s http://localhost:8888/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<your-model>","messages":[{"role":"user","content":"Reply OK"}],"max_tokens":10}' \
  | python3 -m json.tool
# A successful load that crashes on first inference is this trap.
```

**The fix.** On 128 GB unified memory with DFlash speculative decoding, set
`--max-num-seqs 4`. This is not a performance ceiling — at `max-num-seqs=4` the
serve sustained 99.9% turn success over 12 hours of continuous agent traffic.
The card allows up to 32 with DFlash, but that recommendation was not validated
on unified memory. Treat any `max-num-seqs` above 4 as something to soak-test
before trusting, not a safe default.

**Found.** 2026-07-21, during Laguna S 2.1 initial deployment on DGX Spark.

**Attribution.** Nemo (@NemoSMF). Raw soak-test data and the verification suite
are published in the
[NemoKnowledgebase](https://github.com/smfworks/NemoKnowledgebase/benchmarks/laguna-s-2.1-nvfp4/)
and summarized in the
[SMF Clearinghouse blog post](https://www.smfclearinghouse.com/blog/2026-07-25-laguna-s-2-1-soak-test-hardening).
The 12-hour soak was originally run by @Blackwellboy; the `max-num-seqs=4`
finding and the UMA crash were isolated during SMF Works deployment.