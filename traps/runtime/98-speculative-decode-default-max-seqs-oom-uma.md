# Trap 98: speculative-decode max_seqs default OOMs on unified memory under high K

**Found by Nemo ([@smfworks](https://github.com/smfworks)).**

**Status: contributor-measured, conditions as reported** (operational
observation from production serving on DGX Spark GB10, 128 GB UMA; no formal
soak with session/turn counts under this config).

**Symptom.** vLLM launches a model with DFlash speculative decoding using the
default `--max-num-seqs` (256) or the card-recommended value (32), loads weights
successfully, and either crashes during KV cache allocation or crashes within
minutes of real concurrent traffic. The error reads as an OOM, and the natural
response is to lower the utilization fraction -- but the real variable is the
product of `max-num-seqs` and the speculative depth K, which neither the default
nor the card recommendation accounts for.

**Mechanism.** DFlash speculative decoding reserves per-sequence state for each
speculative slot (K tokens), and `--max-num-seqs` multiplies that across all
concurrent sequences. The speculative memory pressure is approximately
proportional to K times seqs. On a discrete GPU with abundant VRAM, the default
of 256 is conservative. On 128 GB unified memory, where the KV pool, the OS, the
tokenizer process, and the model weights all share one physical RAM pool, a high
K x seqs product exhausts memory before the serve can sustain real traffic.

A counter-observation: a 12-hour soak on the same hardware class ran stable at
K=7 / `max-num-seqs=32` (product 224, 409 sessions, 3,099 turns, zero crashes --
[primary data by @Blackwellboy](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/soak/LAGUNA_SOAK_12H_20260725_RESULTS.md)).
The crash reported here occurred at K=15 / `max-num-seqs=32` (product 480). This
suggests the constraint is the product, not seqs alone, and that the threshold
on 128 GB UMA lies somewhere between 224 and 480.

**Stacks and builds bitten.** vLLM 0.25.1, `poolside/Laguna-S-2.1-NVFP4`
revision `b482b5d57fda6e4e562a652869bde24ba2a57c92`, DFlash with K=15
speculative tokens, DGX Spark GB10 128 GB UMA.

- `max-num-seqs=256` (vLLM default): OOM at startup, never reached ready state.
- `max-num-seqs=32` (card-recommended): started, crashed within minutes of
  concurrent agent traffic (2+ simultaneous sessions).
- `max-num-seqs=4`: stable across ~4 days of continuous production agent traffic
  (July 21-25, 2026), no crashes, no OOM events. This is operational observation
  from a coding fleet, not a controlled soak with formal session/turn counts.

GPU memory utilization was 0.82 in all configurations.

**The check.** Before serving with speculative decoding on unified memory:

```bash
# Check what max-num-seqs and K your launch uses
grep -oP 'max-num-seqs\s+\K\d+' <your-launch-script>
grep -oP 'num_speculative_tokens.\D*(\d+)' <your-launch-script>
# Compute the product: K * seqs. On 128 GB UMA, a product above ~224
# is untested and should be soaked before trusting.

# After startup, verify the server handles real concurrent traffic:
curl -s http://HOST:PORT/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<your-model>","messages":[{"role":"user","content":"Reply OK"}],"max_tokens":10}'
# A successful load that crashes on first inference or within minutes
# of concurrent traffic is this trap.
```

**The fix.** On 128 GB unified memory with DFlash speculative decoding, size
`max-num-seqs` with the K x seqs product in mind, not seqs alone. At K=15,
`max-num-seqs=4` (product 60) is stable. At K=7, `max-num-seqs=32` (product 224)
has been soak-tested stable. If you change K, re-derive the seqs ceiling rather
than reusing a value validated at a different K. Treat any K x seqs product
above ~224 as untested on 128 GB UMA until you soak it.

**Found.** 2026-07-21, during Laguna S 2.1 initial deployment on DGX Spark.

**Attribution.** Nemo ([@smfworks](https://github.com/smfworks)). The
counter-observation at K=7 / seqs=32 is from
[@Blackwellboy](https://github.com/Blackwellboy)'s 12-hour soak
([primary data](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/soak/LAGUNA_SOAK_12H_20260725_RESULTS.md)),
cited here with permission.