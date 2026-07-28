# Trap 81: a stopped container has not given the memory back yet

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Measured 2026-07-28 while
bringing up the second arm of the agreement-floor run, on a GB10-class node.
The polling transcript is not published, so a stranger cannot check these
timings. The gate in the check section is what they can run, and running it is
cheaper than checking ours.

It sits next to [trap 13](13-utilization-fraction-on-unified-memory.md), which
is about the memory *fraction*. This one is about the *timing*, and the two get
confused in exactly the way the last section describes.

**Symptom.** You stop the lane that is occupying a node, `docker ps` shows it
`Exited (0)`, you start the next lane, and it dies immediately with

```
torch.AcceleratorError: CUDA error: out of memory
```

The traceback is not from weight loading or from KV cache sizing. It is from
`MemorySnapshot.__post_init__` calling `torch.cuda.mem_get_info` in
`init_device`, which is the very first thing the worker does. The engine never
got as far as reading the checkpoint. Nothing in the message mentions the
container you just stopped, so the obvious readings are all wrong ones: the
node is broken, the image is broken, the gpu-memory-utilization fraction is
too high, another tenant is present.

**Mechanism.** Container exit and device memory reclaim are not the same
event, and `docker ps` reports the first one. The runtime tears down, the
process group goes away, the container object flips to `Exited`, and the
driver is still unwinding the allocation. On unified memory the window is
wider than on discrete cards, because the memory being reclaimed is system
memory that the rest of the machine is also using, and page cache pressure
from anything else running (a large file copy, an image load) competes with
the reclaim.

The failure mode is timing, not capacity. The same launch command that fails
at T+3 minutes succeeds at T+4 with room to spare.

**Measured.** GB10 (DGX Spark class), 121G total. Co-tenant lane running at
`--gpu-memory-utilization 0.86`, stopped and confirmed `Exited (0)`. A launch
issued roughly 3 minutes later failed at `cudaMemGetInfo`. Polling `free -g`
from the moment of the stop, available memory came back to **117G**, and a
launch issued after that gate passed came up normally and served 600 scored
requests without incident. Same node, same image, same arguments, same
checkpoint; the only difference was waiting for a measured condition instead
of an elapsed time.

**The check.** Do not gate lane bring-up on container state, and do not gate
it on a sleep. Gate it on measured free memory:

```bash
# after stopping the co-tenant, before launching anything
for i in $(seq 1 24); do
  avail=$(free -g | awk '/^Mem:/{print $7}')
  echo "gate i=$i avail=${avail}G"
  [ "$avail" -ge "$FLOOR_G" ] && { echo "GATE_PASS"; break; }
  sleep 10
done
```

Pick `FLOOR_G` from what the incoming lane actually needs, not from total
capacity. Print the observed value in the log: if a bring-up later fails, the
gate transcript tells you immediately whether it was memory or something else.

**Why it matters beyond one lost bring-up.** The wrong diagnosis here is
expensive and self-confirming. An operator who reads the OOM as "the fraction
is too high" lowers `--gpu-memory-utilization`, the next launch happens to be
late enough to succeed, and the lower fraction gets recorded as the fix. The
lane then runs for weeks with a smaller KV cache than the hardware supports,
and the real cause is never found. If you are about to reduce a memory
fraction in response to a launch-time OOM, check the clock first.

**Related.** [13](13-utilization-fraction-on-unified-memory.md) for what the
fraction means on unified memory in the first place.
