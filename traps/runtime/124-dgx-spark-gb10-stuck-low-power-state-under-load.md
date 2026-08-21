# Trap 124: DGX Spark / GB10 can get stuck in a low-power state while reporting P0 and high utilization

**Found by Blackwellboy.**

**Status: measured here, raw not published.** First-party NVIDIA DGX Spark (GB10) measurements on 2026-08-21 captured the degraded state, a one-variable complete AC power-removal recovery, matching post-recovery throughput, and a post-recovery longevity observation window. The raw telemetry and benchmark receipts remain in the private BlackwellBench evidence tree; the public numbers below are the sanitized adjudicated summary.

**Hardware scope.**

- **FIRST-PARTY measured:** NVIDIA DGX Spark using GB10.
- **Broader GB10-family / OEM applicability:** corroborated / externally reported only unless separately measured. Do not treat other OEM board or SoC marketing names as synonyms for this first-party DGX Spark / GB10 claim.

**Symptom.** A DGX Spark / GB10 suddenly serves the same model much more slowly even though the workload still reports high GPU utilization, `P0`, cool temperatures, and no active thermal or software power-cap throttle reason. `nvidia-smi -lgc` may accept a requested applications clock without actually raising the observed SM/graphics clock under load.

On the measured unit, sustained load showed approximately:

- GPU utilization: **96%**
- SM/graphics clock median: **799 MHz** (apps/default clock 2418 MHz; max 3003 MHz)
- power draw median: **19.5 W**
- temperature: cool, with no active throttle reason
- sustained BF16: **36.5 TFLOP/s**
- Ornith-1.5-35B-A3B-NVFP4 SGLang Cruz-script decode median: **42.73 tok/s**

The same pinned model/runtime stack had previously been expected near the published Cruz result of about 75 tok/s, so the low serving number initially looked like a runtime/kernel/build reproduction failure.

A full AC power removal changed only the platform power state and produced a coordinated recovery:

| Metric | Before | After | Ratio |
|---|---:|---:|---:|
| SM clock median under sustained load | 799 MHz | 2281 MHz | 2.86x |
| power median under sustained load | 19.5 W | 92.5 W | 4.74x |
| sustained BF16 | 36.5 TFLOP/s | 91.6 TFLOP/s | 2.51x |
| Cruz decode median | 42.73 tok/s | 73.92 tok/s | 1.73x |
| ~43k uncached prefill | 2500.9 tok/s | 5225 tok/s | 2.09x |
| deep uncached prefill | 1033.6 tok/s | 2523.5 tok/s | 2.44x |

Post-cycle decode repeats were 73.92 / 74.02 / 73.89 tok/s, within about 1 tok/s of the published SGLang reference. The 43k uncached prefill result recovered to 5225 tok/s, at or above the published 4839 tok/s reference.

**Mechanism.** The measured mechanism boundary is a **persistent GB10 low-power platform state**: the GPU remains usable and heavily utilized but does not boost into the normal sustained SM-clock/power range, and ordinary software-level controls (including applications-clock lock) do not recover it. A complete AC power removal reset that state; clocks, low-level compute throughput, and model-serving throughput recovered together.

Causal boundary on the measured NVIDIA DGX Spark / GB10 unit: the low-power stuck state is strongly established; complete AC power removal recovered it; the exact PD/EC/SoC firmware root cause is **not** proven. This entry does not claim that a specific USB-C PD firmware, EC firmware, SoC firmware, driver version, or runtime bug is the root cause.

Post-recovery longevity (first-party observation window): after recovery the same unit was observed for **23605 s (~6h33m)** with telemetry samples **505**, decode canaries **26**, BF16 canaries **7**, SM clocks **2385-2405 MHz**, decode **71.47-74.48 tok/s**, BF16 **91.49-92.64 TFLOP/s**, and `LOW_POWER_RECURRENCE=NO`. This does **not** prove a permanent fix or establish a recurrence rate; it proves only that the recovered state remained healthy throughout this observation window.

A prior clock-lock A/B also failed to rescue performance: `nvidia-smi -lgc 2418,2418` applied successfully, but observed SM clocks remained around 0.7-0.8 GHz and Ornith decode stayed about 44.2 tok/s. That rules out "just set the applications clock" as the fix on this state.

**What this does and does not say.** First-party scope is NVIDIA DGX Spark using GB10 only. Broader GB10-family / OEM applicability is corroborated/reported only unless separately measured; other OEM board or SoC marketing names are not synonyms for this first-party GB10 claim. This first-party packet does **not** include a controlled ordinary-reboot survival test as a measured claim - public reports that reboot did not clear similar states are corroboration only. Prefer a true AC power removal over assuming reboot is sufficient. Longevity evidence does not prove permanence or a recurrence rate.

**Stacks and builds bitten.** First-party measurement on an NVIDIA DGX Spark / GB10 system, Ubuntu 24.04.4, kernel `6.17.0-1029-nvidia`, NVIDIA driver `580.173.02`, BIOS revision string recorded privately. The serving workload was `ornith-ai/Ornith-1.5-35B-A3B-NVFP4` under the pinned Cruz SGLang environment (`0.5.18.dev760+ge5a3e4d30`, PyTorch `2.13.0+cu130`, FlashInfer `0.6.17`) and the unchanged Cruz quick/prefill benchmark scripts.

The symptom is platform-level rather than SGLang-specific: before the recovery, the old vLLM lane on the same unit and exact Cruz vLLM/SGLang reproductions all clustered around roughly 44-49 tok/s decode, while quality/agentic scores stayed close to the published reference. That cross-engine pattern is what eventually pushed the investigation below the serving engine.

Independent public reports describe the same symptom family on DGX Spark / GB10 hardware:

- NVIDIA Developer Forums, "DGX Spark (GB10) GPU clock pinned at 721 MHz under full load - no throttling, not liftable via nvidia-smi": https://forums.developer.nvidia.com/t/dgx-spark-gb10-gpu-clock-pinned-at-721-mhz-under-full-load-no-throttling-not-liftable-via-nvidia-smi/376039
- NVIDIA Developer Forums, "DGX Spark Performance Degradation - GPU Power Draw Issue": https://forums.developer.nvidia.com/t/dgx-spark-performance-degradation-gpu-power-draw-issue/361294
- NVIDIA Developer Forums, "GB10 is power limited after crash": https://forums.developer.nvidia.com/t/gb10-is-power-limited-after-crash/366590

Those reports are corroboration only; they do not change this entry's first-party status, do not expand first-party hardware scope beyond NVIDIA DGX Spark / GB10, and do not prove the internal firmware cause.

**The check.** Do not diagnose this from token/s alone. Under a sustained compute load, capture utilization, SM/graphics clock, applications/default clock, power, P-state, temperature, and throttle reasons together:

```bash
nvidia-smi --query-gpu=utilization.gpu,pstate,clocks.sm,clocks.gr,clocks.applications.gr,clocks.max.gr,power.draw,temperature.gpu --format=csv -l 1
```

If a field is unsupported on the installed driver, capture full `nvidia-smi -q` and use the available SM/graphics and power telemetry instead. Pair that telemetry with a sustained low-level compute workload and one unchanged serving canary.

This trap is strongly indicated when all of the following line up:

1. sustained utilization is high (the measured case was ~96%);
2. P-state is nominal (`P0` in the measured case);
3. no ordinary thermal / software power-cap reason is active;
4. SM/graphics clock stays far below the normal sustained applications/boost range;
5. power draw is abnormally low for the same workload;
6. low-level compute **and** LLM serving are both degraded;
7. a complete AC power removal restores clock, power, low-level throughput, and serving throughput together.

A single low clock sample from a short kernel is not enough. The measured diagnosis used sustained load because short kernels can leave telemetry stale or sampled between boosts.

**The fix.** Preserve evidence first, then perform a clean shutdown and a **true power removal**, not merely a reboot. Disconnect power from the DGX Spark long enough for the platform power state to clear; if practical, de-energize the external power supply as well. Reconnect the original rated supply, boot normally, and immediately repeat the same telemetry + low-level + serving checks before changing drivers, runtimes, kernels, or model artifacts.

On the measured unit this restored normal clocks and serving throughput without a Torch rebuild, driver downgrade, FlashInfer change, model change, or runtime tuning.

Do not deliberately induce OOMs/crashes to reproduce the fault. Do not call a firmware update causal unless it is tested separately. If the state recurs, record the trigger and firmware/PD/EC/SoC inventory before changing it; recurrence data is more valuable than an uninstrumented update.

NVIDIA's DGX Spark hardware guide specifies a 240 W external power supply and a GB10 SoC TDP of 140 W, and says the provided 240 W adapter is required for optimal performance: https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf

**Found.** 2026-08-21, during an exact Victor Cruz Ornith-1.5-35B DGX Spark vLLM/SGLang reproduction. Quality reproduced closely while throughput did not. Cross-engine speed loss, passive telemetry, exclusive microbenchmarks, and an ineffective clock-lock A/B narrowed the issue to the host power/clock path. A complete AC power removal then recovered clocks, power, BF16 throughput, decode, and uncached prefill together. A subsequent ~6h33m recovered-state observation window showed no low-power recurrence without proving permanence.

**Attribution.** **Blackwellboy** - first-party finder and measurement. Victor Cruz / @vcruz305 retains credit for the published Ornith DGX Spark serving recipe/reference that made the performance discrepancy measurable. Public NVIDIA forum reporters linked above are credited as independent corroboration of the same GB10 symptom family.

**Related.** [09](09-image-choice-changes-outcome.md) (runtime image changes kernel path), [10](../quantization/10-quant-label-is-not-the-kernel-path.md) (quant label does not prove execution path), [54](../evaluation/54-run-order-and-warm-cache-artifacts.md) (apparent speed changes need controlled A/B), [107](../memory/107-soak-duration-changes-the-verdict.md) (longer observation can change a runtime verdict), [119](../memory/119-free-memory-drifts-down-after-churn.md) (DGX Spark unified-memory state can mislead runtime diagnosis).
