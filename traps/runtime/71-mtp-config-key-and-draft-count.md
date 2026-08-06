# Trap 71: one multi-token-prediction layer does not mean one draft token, and the key is not called what you will grep for

**Found by Blackwellboy.**

**Status: reproduced here** for the config key and its naming, which is in the
checkpoint's own public `config.json`, and **measured here, raw not published**
for the draft count, which came from the engine's cumulative acceptance
counters over 33,659 draft steps on our lane. The counters are not published,
so a stranger can re-derive the key from the checkpoint but has to re-run the
count on their own lane.

**Symptom, three ways.** You grep a checkpoint config for `num_mtp` and conclude
the model has no multi-token-prediction layer. Or you find
`num_nextn_predict_layers: 1`, set `num_speculative_tokens=1`, and get a third of
the speedup that is available. Or you enable it, get the speedup, and later
discover your context capacity dropped by a third and nobody wrote that down.

**Mechanism, and the three facts a deployer needs.**

**1. The key is `num_nextn_predict_layers`.** Together with
`mtp_hybrid_override_pattern: "*E"`. There is no `num_mtp` key in this config,
and `architectures` contains **only** the base architecture string with no second
MTP entry. The MTP layer is addressed through the serving stack's
speculative-decoding path, not through a second architecture in the checkpoint. A
grep for the obvious name returns nothing and the obvious conclusion is wrong.

**2. One layer drafts three tokens.** The single MTP layer uses a shared-weight
design across prediction heads, so the vendor's own serve line drafts **three**
tokens from **one** layer. Reading the config key as a draft count and setting
`num_speculative_tokens=1` leaves most of the benefit on the table. The engine
warns at startup that `num_speculative_tokens > 1` reruns the same shared layer
and "may result in lower acceptance rate", and that is real, but it is a
diminishing return, not a reason to use 1.

Measured acceptance from the engine's counters, 100,977 draft tokens proposed at
exactly 3 per step:

| Position | Accepted | Rate |
|---|---|---|
| 0 | 28,337 | **84.19%** |
| 1 | 22,411 | 66.58% |
| 2 | 17,239 | 51.22% |
| **overall** | **67,987** | **67.33%**, mean 2.02 of 3 |

Acceptance decays roughly linearly with draft depth. At 2.02 accepted per step
the third position is still paying for itself.

**3. It costs KV budget and caps the scheduler, and this is rarely quoted.**
Same checkpoint, same node, the only difference being MTP on or off:

| Arm | KV cache available | KV cache size | Max concurrency at full context |
|---|---|---|---|
| MTP | **30.28 GiB** | 1,175,056 tokens | 6.48x |
| baseline | **35.78 GiB** | 1,562,880 tokens | 9.17x |

**Enabling MTP costs 5.50 GiB of KV budget**, which is 388K tokens of context
capacity, and drops maximum concurrency at full context from 9.17x to 6.48x. It
also silently caps `max_num_scheduled_tokens` at 2048, and costs roughly 130 ms
of TTFT at 1K prompt depth: speculative decoding helps decode and slightly hurts
prefill.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Super 120B A12B NVFP4, vLLM
0.20.0 vendor container, single GB10-class node, 121 GB unified memory.

**The check.**

1. Grep the config for `nextn`, not `mtp`.
2. Read the engine's startup log for the resolved draft architecture and for the
   `max_num_scheduled_tokens` line.
3. Scrape the engine's speculative-decoding counters after a real workload, not
   after a warm-up. Acceptance is content-dependent, so a synthetic prompt gives
   you a number that does not transfer.
4. **Record the KV cache size in both arms.** It is printed at startup and it is
   the number nobody quotes.

**The fix.** Use the vendor's draft count rather than deriving one from the layer
count. Then decide with the whole picture: on this measurement MTP bought 1.78x
median single-stream decode and cost 388K tokens of context capacity plus 130 ms
of TTFT. If your workload is many short completions over long prompts, measure
before assuming it is a win.

**A note on how to establish a speedup like this, which generalises.** The two
arms require separate server processes, so they are **sequential** and arm is
confounded with time. What licenses the causal reading here is not the size of
the effect alone; it is that the **baseline arm is flat to within 0.21 tok/s
across four task categories and three prompt depths**. That flatness rules out
drift, thermals, co-tenancy and time-of-run, because those would have moved the
baseline too and would not sort themselves by content type. The MTP arm's spread,
22 to 31 tok/s, does sort by content type, which is what draft acceptance does by
construction. Quote the control, not just the ratio.

**Negatives recorded.**

- The base architecture and the MTP draft architecture were both present in the
  serving stack's model registry, including in a nightly two minor versions
  older. The registry was never the blocker.
- Baseline-arm capability was **not** measured, so output equivalence between the
  two arms is assumed from design and not verified here. Stated because a reader
  would otherwise assume it was checked.

**Related.**
[trap 11](11-speculative-depth-peak-and-collapse.md) and
[trap 28](28-mtp-fails-only-under-concurrency-or-temperature.md), the
neighbouring speculative-decoding entries;
[trap 36](../evaluation/36-token-cap-is-an-arm-level-handicap.md), which is the
shape of the `max_num_scheduled_tokens` cap becoming an arm-level difference.

**Found.** 2026-07-28.

**Attribution.** Blackwellboy.
