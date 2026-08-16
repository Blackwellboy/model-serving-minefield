# Trap 119: a utilization that worked for weeks starts failing, and the loudest error names the wrong node

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (free-memory decline
captured across four consecutive boots; the reclaim result is reproducible on
any unified-memory box that has been through an OOM-kill).

**Symptom.** A `gpu-memory-utilization` that has served fine for weeks refuses
to boot, with nothing changed in the config:

```
ValueError: Free memory on device cuda:0 (109.53/121.69 GiB) on startup is
less than desired GPU memory utilization (0.91, 110.74 GiB)
```

That line is printed once, early, and quietly. What dominates the log is NCCL
heartbeat and `sendBytes` failures from **every other rank**, so the obvious
read is a fabric problem. We rebooted a node that had nothing to do with it.

The second half of the symptom is what makes it feel unfixable: the number
moves every attempt.

```
112.15  ->  112.05  ->  111.95     (three consecutive boots, config unchanged)
```

Lowering the fraction to fit chases a receding target.

**Mechanism.** On unified memory the GPU and CPU share one physical pool, so
`cudaMemGetInfo`'s "free" tracks `MemAvailable` rather than a dedicated VRAM
free list. Anything holding system memory depresses it: orphaned GPU contexts
left by a previous OOM-kill, pinned buffers, page cache from a large model
download, swap in use. Measured spread on an idle-but-churned node was about
8 GiB — 109.53 GiB while failing against 117.7 GiB after reclaim. That is far
more than the margin a razor-tuned utilization leaves.

Two things then conspire to misdirect the diagnosis:

*Rank 0 fails first, everyone else is louder.* Rank 0 dies on the memory
check; the peers lose it and emit NCCL heartbeat and send errors. Those are
secondary and there are many more of them. Reading the loudest error points
you at the interconnect, which is healthy.

*Auto-retry makes it worse.* Each failed boot orphans a little more, so a
launcher that retries on this failure degrades the exact quantity it is
retrying against. That is the descending sequence above, and it is why the
ceiling looks non-deterministic rather than merely low.

This is the temporal sibling of
[13](13-utilization-fraction-on-unified-memory.md), which covers the static
semantics — a fraction reserved against the pool the OS also needs. Trap 13
explains why the headroom is thin; this entry is about the headroom moving
underneath a config that was already tuned, and about the error that surfaces
belonging to the wrong rank. See also
[96](96-list-devices-reports-host-memory-as-device-free-memory.md) for the
device-listing version of host memory being reported as device free memory.

**Stacks and builds bitten.** vLLM `v0.23.1rc1.dev190+gab6660699` and
`v0.1.dev17863+ge232d2623.d20260715`; GLM-5.2 as `QuantTrio/GLM-5.2-Int4-Int8Mix`
and as a W4W8 community build; 200K-600K context, `fp8_ds_mla` KV, TP=4 over
four DGX Spark (GB10, sm_121a, aarch64, 121.69 GiB unified per node), driver
580.142.

Expected on any unified-memory device of this class, not only Spark. Driver
590.48.x carries a separate UMA-not-released-on-exit regression that would
compound it.

**The check.** Grep for the first exception rather than the loudest:

```bash
docker logs <container> 2>&1 | grep -m1 -B2 -A2 "Free memory on device"
```

Then compare what the allocator will see against a known-good baseline:

```bash
grep MemAvailable /proc/meminfo     # what cudaMemGetInfo reports as free
free -g | awk '/Swap:/{print "swap in use:", $3"G"}'
```

`MemAvailable` several GiB under a freshly-rebooted baseline, with NCCL noise
on the other ranks, is this trap and not the fabric.

**The fix.** Reclaim before boot. Do **not** lower `gpu-memory-utilization`:
that trades a permanent reduction in KV pool for a transient condition, and it
will not hold anyway while the number is still drifting.

```bash
sudo fuser -k -9 /dev/nvidia*       # orphaned GPU contexts
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches
sudo swapoff -a && sudo swapon -a
```

This restored 109.53 -> ~117.7 GiB and the original utilization booted
unchanged. It is now a pre-boot step in the launcher rather than a thing
someone remembers to do.

Also disable auto-retry for this specific failure. Retrying strictly worsens
the input condition, and it converts a legible one-shot error into a moving
target that reads as flaky hardware.

**Found.** 2026-08-15, after a 433 GB model download and a run of OOM-killed
boots on one node. Cost several hours and one unnecessary reboot of an
uninvolved node before we read the primary exception instead of the loudest
one.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Reported as
[#45](https://github.com/Blackwellboy/model-serving-minefield/issues/45).
