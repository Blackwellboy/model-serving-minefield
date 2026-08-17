# Trap 119: a utilization that worked for weeks starts failing, and the loudest error names the wrong node

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (free-memory decline
captured across four consecutive boots; the reclaim result was measured on the
reported DGX Spark lane).

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
host-side pressure and CUDA-visible free memory are not independent quantities.
On the reported GB10 lane, `MemAvailable` and the free-memory value seen by the
runtime moved together as model-download page cache, orphaned GPU contexts,
pinned buffers and swap consumed or released the shared pool. That observation
should not be read as a universal identity between Linux `MemAvailable` and
`cudaMemGetInfo` on every UMA stack; the useful diagnostic is that pressure in
one shared pool can reduce both.

Measured spread on an idle-but-churned node was about 8 GiB — 109.53 GiB while
failing against 117.7 GiB after reclaim. That is far more than the margin a
razor-tuned utilization leaves.

Two things then conspire to misdirect the diagnosis:

*Rank 0 fails first, everyone else is louder.* Rank 0 dies on the memory
check; the peers lose it and emit NCCL heartbeat and send errors. Those are
secondary and there are many more of them. Reading the loudest error points
you at the interconnect, which is healthy.

*Auto-retry makes it worse.* On this lane, repeated failed boots left the
reported free-memory value slightly lower on each attempt. An auto-retry loop
therefore made the input condition worse while hiding the original primary
exception under secondary distributed errors.

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

The general risk applies to unified-memory systems where the serving runtime
and the operating system compete for the same physical pool. The exact
relationship between OS counters and CUDA-visible free memory remains
platform/driver specific.

**The check.** Grep for the first exception rather than the loudest:

```bash
docker logs <container> 2>&1 | grep -m1 -B2 -A2 "Free memory on device"
```

Then compare both OS-visible pressure and the runtime's own free-memory reading
against a known-good baseline before blaming the fabric:

```bash
grep MemAvailable /proc/meminfo
free -g | awk '/Swap:/{print "swap in use:", $3"G"}'
```

If host availability is several GiB under a known-good baseline and the
runtime's free-memory check is failing on the same node while peers only emit
secondary NCCL noise, reclaim shared-pool pressure and retry once before
changing fabric settings or permanently shrinking the KV reservation.

**The fix.** Stop known serving/model-download processes cleanly and reclaim
transient pressure before boot. Do **not** immediately lower
`gpu-memory-utilization`: that can trade a permanent reduction in KV pool for a
transient condition.

On a **dedicated node only, during a maintenance window**, the contributor used
this destructive reclaim sequence after confirming no wanted GPU process would
be killed:

```bash
sudo fuser -k -9 /dev/nvidia*       # destructive: kills GPU users
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches
sudo swapoff -a && sudo swapon -a
```

Do not run that blindly on a shared workstation or multi-tenant host. Prefer
identifying and stopping the owning processes first; use cache/swap reclaim only
when you understand the operational impact.

On the reported node this restored 109.53 -> ~117.7 GiB and the original
utilization booted unchanged.

Also disable blind auto-retry for this specific startup failure. Repeated
retries can obscure the first useful exception and, on the measured lane,
coincided with progressively lower available memory.

**Found.** 2026-08-15, after a 433 GB model download and a run of OOM-killed
boots on one node. Cost several hours and one unnecessary reboot of an
uninvolved node before we read the primary exception instead of the loudest
one.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Reported as
[#45](https://github.com/Blackwellboy/model-serving-minefield/issues/45).
