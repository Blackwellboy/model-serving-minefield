# Trap 118: a healthy multi-node boot looks deadlocked because the driver log is silent by configuration

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (driver log and
per-node worker session logs captured over the same wall-clock window; the
launcher flag that causes it is in the public launch script).

**Symptom.** A four-node boot stops producing output. The driver log's last
substantive line is a placement-group message timestamped ten or more minutes
ago. Ray reports the cluster healthy, `4.0/4.0 GPU`, placement group filled.
The only new line arrives once a minute:

```
INFO ... [shm_broadcast.py:705] No available shared memory broadcast block
found in 60 seconds
```

which reads exactly like a stalled collective. We diagnosed a hung NCCL
init, tore the cluster down, "fixed" NCCL settings and relaunched. Three
times. It was never hung, and each teardown cost a fresh nine-minute reload.

**Mechanism.** The launcher starts every node with

```
ray start ... --include-log-monitor=false --disable-usage-stats ...
```

Ray's log monitor is the component that forwards actor stdout and stderr to
the driver. With it off, **no worker output ever reaches the head log** — not
NCCL, not weight loading, not compile. All of it lands in each node's own Ray
session directory and nowhere else.

Meanwhile the head genuinely is idle, because it is waiting on workers, and
the one message you do get is misleading: `shm_broadcast` "No available shared
memory broadcast block" is an INFO-level poll, not an error. The single signal
available actively argues for the wrong conclusion.

What was happening during the silence, read off a worker instead:

```
NET/IB : Using [0]<HCA>:1/RoCE [RO]; OOB <IFACE>:<NODE_IP><0>
Connected all rings, use ring PXN 0 GDR 0
ncclCommInitRank comm 0x<ADDR> rank 2 nranks 4 ... - Init COMPLETE
Filesystem type for checkpoints: NFS. Checkpoint size: 377.63 GiB.
Loading weights took 538.63 seconds
Model loading took 96.94 GiB and 581.4 seconds
torch.compile took 53.10 s in total
```

502 `NCCL INFO` lines on the worker; zero on the driver. The quiet window was
a nine-minute NFS weight load, which is indistinguishable from a deadlock if
you are reading the only file that is guaranteed not to mention it.

**Stacks and builds bitten.** vLLM `v0.1.dev17863+ge232d2623.d20260715` with
`--distributed-executor-backend ray`, CUDA 13.2, driver 580.159.03; GLM-5.2
W4W8 (compressed-tensors community build), 600K context, `fp8_ds_mla` KV, MTP
k=6, TP=4 with decode-context-parallel 4, across four DGX Spark (GB10,
sm_121a, aarch64) nodes, weights NFS-mounted read-only from one node.

Any Ray-backed vLLM deployment whose launcher passes
`--include-log-monitor=false` is exposed. Several published DGX Spark launch
scripts set it, reasonably, to cut log noise.

**The check.** Before calling a Ray deploy hung, read a worker rather than the
driver:

```bash
docker exec <worker-container> bash -lc \
  'tail -5 $(ls -t /tmp/ray*/session_latest/logs/worker-*.out | head -1)'
```

Progress there while the head is silent means it is not hung. Two liveness
discriminators that need no logs at all:

```bash
docker exec <container> bash -lc 'ps -eLo pcpu,comm --sort=-pcpu | head -3'
# a worker pinned near 100% CPU is loading or compiling, not deadlocked

grep -c "No available shared memory broadcast" <driver-log>
# INFO-level poll: a rising count on its own is not evidence of failure
```

**The fix.** Drop `--include-log-monitor=false` from `ray start` so worker
output reaches the driver. If you keep it off, document the per-node session
log path beside the launcher, because that is now the only place progress
exists.

Separately, budget the weight load explicitly before setting any hang timeout.
Ours was 538 s for ~97 GiB per rank off NFS; any timeout shorter than that
manufactures false positives on a working cluster. Related: the KV-side
version of "quiet is not broken" is [106](../memory/106-kv-occupancy-ceiling-is-not-a-leak.md).

**Found.** 2026-08-16, deploying a 415 GB GLM-5.2 checkpoint across four nodes
with weights served over NFS from a single head node.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Reported as
[#44](https://github.com/Blackwellboy/model-serving-minefield/issues/44).
