# Trap 98: speculative depth and sequence capacity coincide with OOMs on unified memory

**Found by Nemo ([@smfworks](https://github.com/smfworks)).**

**Status: contributor-measured, conditions as reported** (operational
observation from production serving on DGX Spark GB10, 128 GB UMA; no formal
soak with session/turn counts under this config).

**Symptom.** vLLM launches a model with DFlash speculative decoding using the
default `--max-num-seqs` (256) or the card-recommended value (32), loads weights
successfully, and either crashes during KV cache allocation or crashes within
minutes of real concurrent traffic. Lowering `max-num-seqs` to 4 under the same
reported K=15 configuration coincided with stable operation.

**Candidate mechanism, not isolated by these observations.** Speculative depth
and sequence capacity can both contribute to memory pressure, so a
`max-num-seqs` value validated at one K must not be assumed safe at another K
on 128 GB unified memory. The observations are consistent with K and sequence
capacity contributing jointly, but they do not establish direct K x seqs
scaling, a universal product threshold, or the relative contribution of other
configuration and workload variables.

The contributor observed the failure at K=15 / `max-num-seqs=32` and stable
operation at K=15 / `max-num-seqs=4`. Separately, a 12-hour soak by
@Blackwellboy on the same hardware class was stable at K=7 /
`max-num-seqs=32`
([primary data](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/soak/LAGUNA_SOAK_12H_20260725_RESULTS.md)).
That is a counter-observation under a different K, not a matched control and
not evidence for a threshold between the two configurations.

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
# Record the actual max-num-seqs and K; do not classify by either value alone.
grep -oP 'max-num-seqs\s+\K\d+' <your-launch-script>
grep -oP 'num_speculative_tokens.\D*(\d+)' <your-launch-script>
```

Then, on the actual configuration and only under already-authorised traffic or
a disposable test surface, record these outcomes separately:

1. whether the process reaches ready state;
2. whether the first bounded request completes;
3. whether the declared concurrency level completes without OOM; and
4. the observation interval before OOM or the end of observation.

Report `startup OOM`, `first-request OOM`, `OOM under bounded concurrency`, or
`no OOM during <declared interval>` rather than a single pass/fail. A
low-K/high-sequence or high-K/low-sequence configuration cannot inherit a pass
from another configuration: the result applies only to the exact K, sequence
capacity, workload and observation interval recorded.

**The fix.** On the reported 128 GB unified-memory configuration with DFlash
K=15, lowering `max-num-seqs` from 32 to 4 was the working mitigation. Treat
that as a configuration-specific observation, not a universal ceiling. If K,
sequence capacity, model, memory-utilisation setting or workload changes,
repeat the staged check above rather than carrying forward a value validated
under different conditions.

**Found.** 2026-07-21, during Laguna S 2.1 initial deployment on DGX Spark.

**Attribution.** Nemo ([@smfworks](https://github.com/smfworks)). The
counter-observation at K=7 / seqs=32 is from
[@Blackwellboy](https://github.com/Blackwellboy)'s 12-hour soak
([primary data](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/soak/LAGUNA_SOAK_12H_20260725_RESULTS.md)),
cited here with permission.
