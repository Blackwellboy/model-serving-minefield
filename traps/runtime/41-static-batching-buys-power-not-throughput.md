# Trap 41: static batching bought power, not throughput

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-12 and 2026-07-13 entries).**

**Status: reported by others.**

**Symptom.** You batch your generation loop to go faster. GPU utilization
climbs from 80% to 100%, power draw rises from 224 W to the 300 W cap, every
dashboard says the machine is working harder, and the job finishes in the
same time. Measured: **12.1 seeds/min after batching versus 12.4 before**, no
significant difference. Utilization went up, work did not.

The reason this misleads rather than merely disappoints is that 100% GPU
utilization is the metric everyone reaches for to confirm a throughput fix.
Here it confirmed nothing: utilization measures whether the GPU is busy, not
whether it is busy on your results.

**Mechanism.** A static batch finishes when its **longest** sequence
finishes. Every other row in the batch keeps occupying its slot, and keeps
being computed, long after it has emitted its stop token. The sequential
version had no such tax: each generation returned at EOS and the next one
started immediately. For a workload with a wide length distribution, the
straggler tax cancels almost exactly the arithmetic gain from batching, which
is what produced the flat result here.

The busy-work is real compute, which is why utilization and power rise. It is
padding.

The fix is continuous batching, where a finished sequence is evicted and a
waiting one takes its slot within the same step. Moving the identical
workload to a vLLM lane took it to **171 seeds/min**, about 14x the HF
sequential rate, and finished a 4,614-item backlog in 27 minutes.

**Stacks and builds bitten.** HF transformers `generate()` with static
batching (W=8, 32 sequences per call) on 2x RTX PRO 6000, Qwen3.6-35B-A3B
bf16, a self-generation workload with a wide output-length distribution.
Compared against vLLM serving the same weights on the same hardware. The
class applies to any hand-rolled batching loop over a variable-length
workload; it is not specific to this model or this framework.

**The check.** Measure completed **items per minute**, end to end, before and
after any batching change. Do not accept GPU utilization, power draw, or
tokens/second as evidence, because all three rise when the batch is padding.

```python
# the only number that settles it
t0, done = time.time(), 0
for item in workload:
    ...
    done += 1
print(f"{done / ((time.time() - t0) / 60):.1f} items/min")
```

If items/min did not move, look at your length distribution: compute the
ratio of the longest to the median output length in a batch. If that ratio is
large, static batching cannot help you and the straggler is the reason.

**The fix.** Use continuous batching (vLLM or equivalent) rather than a
static batch loop, for any workload whose outputs vary in length. If you must
stay in-framework, bucket by expected output length so that rows in a batch
finish together, which recovers part of the gain, or accept the sequential
path and do not pay the power.

Two setup notes from the finder's vLLM migration, both of which cost him time
before the lane ran: on a hybrid linear-attention architecture the Mamba-style
cache imposed a hard ceiling on concurrent sequences (`max_num_seqs` 1024
exceeded a limit of 748, resolved at 256), and the endpoint URL had `/v1`
appended twice. He also installed vLLM into an isolated virtualenv rather
than the training environment, specifically so a failed migration could not
take the training and eval stacks with it.

**Found.** 2026-07-12 (the negative batching result) and 2026-07-13 (the
continuous-batching comparison on the same workload).

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who published the negative result with its numbers rather than quietly
reverting the change.
