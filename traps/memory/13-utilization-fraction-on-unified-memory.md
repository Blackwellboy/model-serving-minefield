# Trap 13: gpu-memory-utilization fractions misbehave on unified memory

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Measured on DGX Spark class
hardware; the rows are not published, so nothing below is checkable by
reading our data. The check is runnable on any unified-memory box, and the
fixed-bytes fix pattern is public in our container recipe. This entry becomes
"reproduced here" when either the raw lands or the check grows a pass/fail
assertion a reader can run.

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

## Added 2026-07-28: the pressure arrives host-side, not as a CUDA OOM

**NVIDIA Nemotron 3 family, three checkpoints (Nano 30B A3B NVFP4, Nano Omni 30B A3B NVFP4, Super 120B A12B NVFP4), GB10-class single nodes, vLLM 0.20.0 and 0.25.1**, on 121 GB unified-memory nodes. Default utilisation on one build
(0.92 effective) sized a KV pool of 29.7M tokens for a 19 GB-weight model and
took host RAM to **118 of 121 GB**. At an explicit 0.90 on a 74.8 GiB
checkpoint, **115 of 121 GB** with the server idle, about 6 GB of headroom.

The detail worth adding: on unified memory the KV pool and the operating system
compete for the same physical RAM, so the failure **does not look like a GPU
problem and will not be diagnosed as one**. There is no CUDA OOM to find. It is
correct behaviour for a dedicated node and dangerous the moment anything else
has to run there.

*Status of this addendum: measured here, raw not published.*
