# Trap 13: gpu-memory-utilization fractions misbehave on unified memory

**Status: measured on our fleet** (raw not published); the fixed-bytes fix pattern is public in our container recipe.

**Symptom.** A unified-memory box (DGX Spark class, 121 GiB usable) sits at
119 of 121 GiB used with under 2 GiB available for the OS, or conversely a
conservative utilization fraction strands tens of GB that the KV cache
could be using. Sessions swap, sibling processes die, or capacity quietly
goes unused, and none of it looks like a config problem.

**Mechanism.** `--gpu-memory-utilization` is a fraction of total device
memory. On a discrete GPU the remainder is VRAM headroom; on unified memory
the "device" is also the system's RAM, so the fraction reserves against the
same pool the OS, the tokenizer processes, and every other service need.
The reservation is also opaque: you cannot tell from the flag how many KV
tokens you actually bought, and model-size changes silently change it.

**Stacks and builds bitten.** vLLM on DGX Spark GB10 fleet boxes. Measured
internal audit: util 0.75 on a 121 GiB box reserved ~60 GB against unified
memory and left MemAvailable at 1.9 GiB with swap engaged, a margin one
extra concurrent session could blow. Separately, oversized context settings
on sibling lanes re-inflated reservations after every restart and kept a
node permanently at the memory ceiling.

**The check.** After serving, read actual KV pool size from the server logs
and `MemAvailable` from the OS, and ask whether either number was chosen or
merely happened.

**The fix.** On unified memory, pin the KV cache in bytes instead of by
fraction. Our production Laguna recipe runs
`--kv-cache-memory-bytes 12884901888` (12 GiB, ~327K fp8-KV tokens), chosen
deliberately, stable across restarts, with the arithmetic documented next
to it ([container recipe](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/container)).
The flag pair to know: fraction for throwaway experiments, bytes for
anything shared or long-running.

**Found.** 2026-07-02 (memory-pressure audit), fix pattern published
2026-07-23.

**Attribution.** Blackwellboy.
