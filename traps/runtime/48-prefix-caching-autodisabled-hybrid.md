# Trap 48: prefix caching silently auto-disabled for hybrid/recurrent architectures

**Found by TheTom.**

**Status: reproduced here.** Measured on both engines with the same model family and the same agent
traffic shape; raw logs held outside the tree; can be produced on request, per the default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo).

**Symptom.** An engine documented as having prompt/prefix caching re-prefills the **entire**
conversation on every agent turn. Time-to-first-token stays flat as the conversation grows instead
of collapsing after turn one. Any "agentic throughput" comparison against another engine is then
measuring two different workloads while appearing to measure two engines.

**Mechanism.** vLLM **auto-disables** prefix caching for hybrid mamba/DeltaNet models, because the
recurrent state is not checkpointable in that path. It says so once, in the startup log, and never
again:

```
enable_prefix_caching=False
```

Meanwhile a llama.cpp-family server checkpoints the recurrent state and reports **97 to 100% cache
hits** on the identical traffic (`cache=58055/59835` and similar in agent logs).

**Stacks and builds bitten.** vLLM 0.24-era serving hybrid Gated-DeltaNet / Mamba architectures.
Confirmed on a Qwen3.6-27B hybrid-linear-attention checkpoint. Not a flag you can override, it is a
capability gate.

**The check.** Two lines:

```bash
# 1. the log line, at startup
grep -i 'enable_prefix_caching' server.log

# 2. behavioral: same conversation, three consecutive turns; TTFT must fall after turn 1
python3 checks/cache_hit_probe.py --base-url $URL --model $M --turns 3
```

Runnable: [`checks/cache_hit_probe.py`](../../checks/cache_hit_probe.py), sends a growing
conversation and reports TTFT per turn plus any server-reported cache ratio.

```
$ python3 checks/cache_hit_probe.py --base-url $URL --model $M --turns 3
  turn 1 TTFT 5.48s   turn 2 TTFT 5.51s   turn 3 TTFT 5.55s
  VERDICT: flat TTFT across turns, prefix cache is not engaging
```

**The fix.** None client-side; choose the engine by **workload shape**, and state the shape whenever
you publish a throughput number for a hybrid model:

- **Cold, long-context, one-shot** (fresh 30K prompt to short answer): the re-prefilling engine
wins,
  roughly **2x faster TTFT**.
- **Growing agent conversation**: the caching engine wins, because cached turns are decode-bound.

Measured on the same model, same box, prefill = 4,030-token prompt to 5-token reply, decode =
24-token prompt to 400-token generation, greedy, single request, warm server:

| | llama.cpp + MTP | vLLM, no MTP | vLLM + MTP |
|---|---|---|---|
| prefill tok/s | 3,400 | 6,530 | **6,636** |
| decode tok/s | **109** | 63.8 | 97.9 |

The prefill advantage largely evaporates under real agent traffic where the caching engine hits
97 to 100%. Neither column is "the faster engine."

**Correction worth copying.** Our first writeup claimed the vLLM side capped at 32K context. That
was
**our own** conservative `--max-model-len`, set during an unrelated OOM fight and never re-probed , 
the KV pool actually held 93,934 tokens (visible in the `GPU KV cache size` log line). The real
structural gap was prefix caching, not context. Re-probe your own limits before attributing them to
the engine.

**Found.** 2026-07-11.

**Attribution.** TheTom.
