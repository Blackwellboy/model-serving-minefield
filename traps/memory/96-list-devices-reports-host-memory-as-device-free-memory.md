# Trap 96: `--list-devices` reports host available memory as device free memory, and prints a free figure larger than the card's own total on the same line

**Found by Blackwellboy.** Found while capturing device banners during the
coverage pass on a target supplied by Exile; no model was loaded for this probe.

**Status: reproduced here**, 2026-07-28, llama.cpp `b9878-2da668617` under WSL2
on Windows, two consumer GPUs. The output contradicts itself, so a reader can
confirm it from one command without trusting our numbers.

**Evidence pointer.** One `--list-devices` invocation, compared against
`nvidia-smi` at the same instant.

**Symptom.** A capacity decision, a slot count, or a context size is sized from
the serving binary's own device listing, and allocation fails anyway. Or two
very different cards report the same free memory.

## Symptom, captured

Captured while one card was almost entirely consumed by a live lane and the
other was empty:

```
nvidia-smi:
  GPU 0  RTX 5090   total 32607 MiB   used     4 MiB   free 32183 MiB
  GPU 1  RTX 3090   total 24576 MiB   used 24031 MiB   free   292 MiB

llama-server --list-devices, same instant:
  CUDA_VISIBLE_DEVICES=0 -> CUDA0: NVIDIA GeForce RTX 5090 (32606 MiB, 43779 MiB free)
  CUDA_VISIBLE_DEVICES=1 -> CUDA0: NVIDIA GeForce RTX 3090 (24575 MiB, 43781 MiB free)
```

The 3090 has **292 MiB** actually free. llama.cpp reports **43781 MiB** free, a
150-fold over-report, on a card whose stated total in the same parenthesis is
24575 MiB.

## Mechanism

The reported figure is **host** available memory, not device memory:

```
/proc/meminfo MemAvailable: 44852248 kB = 43801 MiB
```

43781 against 43801 MiB. Both GPUs report essentially the same value regardless
of their very different capacities, and the value drifts between invocations in
step with host RAM: 43530, then 43779 MiB, minutes apart, on an unchanged GPU.
On this platform the free-memory query returns host availability, and llama.cpp
faithfully prints what it is given.

## Why it is dangerous rather than cosmetic

- **It errs toward availability.** A planner that sizes context or slot count
  from this number will believe it has 43 GiB on a 24 GiB card with 292 MiB
  free, and will discover otherwise at allocation time.
- **It is identical across cards**, so it cannot be used to choose a device
  either.
- **It looks authoritative.** It comes from the serving binary itself, not a
  third-party tool, which is exactly the source an operator would trust over
  `nvidia-smi`.
- **It survives the obvious sanity check.** The value is plausible in absolute
  terms, since 43 GiB is a believable number for a GPU, and only becomes absurd
  when compared against the total printed beside it.

## The check is one line and it is portable

The output contradicts itself, so no external reference is needed:

```
assert free_mib <= total_mib   # per device, from --list-devices
```

That is a strict inequality violation on this platform, which makes it a clean
fail rather than a judgement call. Anything reading free VRAM for capacity
decisions should take it from the driver
(`nvidia-smi --query-gpu=memory.free`), not from the serving binary, and should
assert the above before trusting either.

## Relationship to the queued unified-memory candidate

This is the same class as the queued candidate about llama.cpp cache and
unified-memory reporting nonsense, which had been recorded as needing
unified-memory hardware we could not free up. **It does not need that
hardware.** WSL2 on a discrete-GPU desktop reproduces host memory being reported
as device memory. The candidate moves from blocked-for-hardware to reproduced in
an adjacent configuration, with the caveat that we have shown it for the
*reporting* path only: the cache-sizing consequences the candidate also alleges
were not tested here and remain open. The disposition is recorded in
[the R2 llama.cpp queue note](../../mining/2026-07-28-r2-llamacpp-queue-dispositions.md).

## Scope

llama.cpp `b9878-2da668617` under **WSL2**, two consumer GPUs. The mechanism is
a platform memory-reporting property and we would expect it wherever the CUDA
free query returns host availability; we have **not** checked native Linux, and
it may well be correct there. This is not a property of any model, and no model
was loaded for the probe. No capability claims.

**Related.**
[Trap 13](13-utilization-fraction-on-unified-memory.md) is the allocation-side
version of the same confusion between host and device pools.

**Found.** 2026-07-28, incidentally, while capturing device banners for a
cross-architecture comparison.
