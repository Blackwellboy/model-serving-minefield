# Trap 139: stock NCCL round-robins both HCAs at the ring successor, so on a switchless triangle rank 0 talks to rank 2 over the cable that physically goes to rank 1

**Found by @btcxoomer.**

**Status: contributor-measured, conditions as reported.** Measured on the
contributor's own three-node DGX Spark (GB10) switchless triangle over direct
QSFP RoCE links, 2026-09-05. The check below is a procedure a stranger with a
3-node multi-NIC mesh can run on their own hardware; the contributor's raw
`NCCL_DEBUG=INFO` logs are not published here.

**Symptom.** A 3-node tensor-parallel bring-up on a switchless triangle (each
node has two HCAs, each HCA cabled to a *different* peer, no switch) fails with
a QP timeout in which the local and remote GIDs belong to nodes that have **no
physical path between them**. Concretely, from the contributor's logs:

```
NCCL INFO Call to ibv_modify_qp failed with 110 Connection timed out,
on dev <hca>:1, local GID ::ffff:<A-to-B leg IP>, remote GID ::ffff:<C-to-B leg IP>
```

Fabric addresses and the HCA device name are redacted; the point is that the
two GIDs sit on legs of two different nodes with no shared subnet. Node A's
rail toward B tries to reach node C's rail toward B. A has no route to
that subnet and no cable to C on that interface.

**Read the symptom carefully, because the natural misreading is wrong.** This
is not a detour through the intermediate node: rank A never reaches C via B.
A's direct cable to C exists and works; the defect is **egress device
selection**. NCCL sends traffic destined for C out the interface physically
cabled to B, which has no path to C's GID, and the QP times out against an
unreachable address. The failure mode is a dead end, not a mis-routed
through-path. (The ring *algorithm* legitimately hops A to B to C; that is
normal ring all-reduce and is not this trap.) The failure reproduced identically on
**2/2 independent surfaces**: a real vLLM TP=3 start and an isolated two-line
`torch.distributed` all-gather in the same pinned image. So it is not a vLLM
bug, not a cable fault, and not a GID hole.
Operators burn hours on wiring, IPs, and GID indices, all of which were already
correct.

**Mechanism.** Stock NCCL builds its channel map by **round-robining all
selected HCAs against each rank's single ring successor**, as a load-balancing
choice. With two HCAs, half of every rank-0-to-rank-1 channel set is assigned to
the second HCA. On a star or switched fabric that is harmless: any interface can
reach any peer. On a switchless triangle each HCA reaches exactly one peer, so
NCCL schedules a fraction of every peer pair's traffic onto the leg that
physically connects the *other* two nodes. The QP never resolves; the symptom is
a timeout against an unreachable GID, which reads like a broken fabric.

The contributor's `NCCL_DEBUG=INFO` channel map, captured inside the pinned
serving image with a `torchrun` all-gather:

```
Channel 00/0 : 0[0] -> 1[0] via NET/IB/0
Channel 01/0 : 0[0] -> 1[0] via NET/IB/1   <-- alternates BOTH HCAs vs ONE peer
```

What did **not** fix it: **4/4 attempted configuration changes left the
channel map unchanged and the timeout identical**: re-planning subnets per leg,
`NCCL_IB_ADDR_RANGE` covering all three /24s, `NCCL_CROSS_NIC=1`, and a verified
clean same-index RoCEv2 GID on all six HCAs. A single
`NCCL_IB_HCA` cannot form the ring at all: one NIC reaches one peer, and a
3-cycle needs each node to reach two. Perfect same-index wiring is
mathematically impossible on a triangle (a 3-cycle needs 3 colors for a proper
2-edge-coloring), so this is not fixable at the wiring level; the fabric must be
routed per destination.

**Stacks and builds bitten.** Stock NCCL (the pip-path `libnccl.so.2` bundled in
NGC-class vLLM images) on multi-NIC switchless meshes. Observed on
`ghcr.io/miaai-lab/glm-5.3-flash-2x-dgx-sparks@sha256:9bb1557a` (EXL3 recipe
image) serving a GLM-family checkpoint at TP=3 across three DGX Spark (GB10)
nodes over RoCEv2 (MTU 9216, two HCAs per node, distinct /24 per leg), in both
the vLLM start path (via `torch.distributed`) and a bare `torchrun` all-gather
in the same image. The stock build ignored `NCCL_IB_SUBNET_AWARE_ROUTING=1`;
the exact stock NCCL version string was not recorded before the library was
replaced, so this entry does not name it. Engine-independent: the defect is NCCL's NIC selection,
not the serving stack. A 4-node ring attempt by the same operator produced the
same class of failure via a different surface message
(`NCCL WARN ... no local PF shares a /24 with peer GIDs`).

**The check.** On any 3-node multi-NIC mesh, before wiring a model into it, run
the cheapest decisive probe inside the image you intend to serve with:

1. `torchrun` a two-line `torch.distributed` all-gather across the three nodes
   with `NCCL_DEBUG=INFO` and both HCAs in `NCCL_IB_HCA`.
2. Grep the channel map: `grep 'via NET/IB' <log> | sort | uniq -c`.
3. **TRAP PRESENT:** each peer pair shows channels on *both* `NET/IB/0` and
   `NET/IB/1` while each HCA is cabled to a different peer. The run fails with
   `ibv_modify_qp failed with 110` naming a local/remote GID pair with no
   physical path.
4. **TRAP ABSENT:** every channel's chosen device corresponds to the leg that
   actually reaches that peer (either single-HCA per destination by design, or
   subnet-aware selection), and the all-gather completes.

A run that *succeeds* on a triangle with stock NCCL is not evidence the trap is
absent; check the channel map, because a working ring may simply have been
scheduled onto legs that happen to be reachable.

**The fix.** Use NCCL that selects the NIC **per destination subnet**, and force
a topology that does not need a switch:

```
NCCL_ALGO=Ring                      # tree/CollNet need a switch this mesh lacks
NCCL_SKIP_TREE_CONNECT=1
NCCL_IB_SUBNET_AWARE_ROUTING=1
SUBNET_PREFIX_LEN=24                # distinct /24 per leg
NCCL_CROSS_NIC=1
NCCL_IB_GID_INDEX=3                 # after verifying slot 3 is RoCEv2 on every HCA
NCCL_MIN_NCHANNELS=4 NCCL_MAX_NCHANNELS=4
NCCL_IB_HCA=<both HCAs>
```

Whether `NCCL_IB_SUBNET_AWARE_ROUTING=1` works as a plain env var depends on the
NCCL build: the contributor's stock image ignored it (that is the trap above),
and the fix that worked was a **patched `libnccl.so.2` (2.30.7, subnet-aware
routing compiled in) baked into a derived image** that overwrites the pip-path
copy (`/usr/local/lib/python3.12/dist-packages/nvidia/nccl/lib/libnccl.so.2`).
With that library and the envelope below, the triangle came up clean: zero
NCCL warnings in the channel bring-up, and the first API call served correctly
(1/1).
Delivery matters: `VLLM_NCCL_SO_PATH` / `LD_LIBRARY_PATH` retarget only vLLM's
pynccl loader while `torch.distributed` still maps the stock library (split
brain, same timeout), and `LD_PRELOAD` trips duplicate-NCCL asserts in images
that bundle DeepEP. The derived-image `COPY` is the only clean path the
contributor found. Two secondary consequences on the triangle: without
`NCCL_ALGO=Ring` NCCL defaults to CollNet/tree and dies with
`NCCL WARN Rank N has no transport for recv peer M`; and in one vLLM build
CUDA-graph capture at warmup hit a strong-stream failure on the mesh
(`ncclStrongStreamAcquire`, "CUDA driver is a stub library") and had to be
disabled (`cudagraph_mode=NONE`), forfeiting graph decode speed.

**Claim boundary.** May claim: stock NCCL's HCA round-robin against the ring
successor makes a switchless multi-NIC triangle false-fail as "broken fabric";
the channel map is the decisive diagnostic; per-destination subnet routing
(verified here only via a patched library) is required on this topology. Must
not claim: that every NCCL version ignores the env var (newer builds may ship
it working; the contributor's stock build did not), that switched fabrics are
affected, or specific throughput numbers for the patched configuration.

**Found.** 2026-09-05, during a 3-node DGX Spark TP=3 bring-up, after the same
diagonal had already killed a 4-node ring attempt on the same fleet.

**Attribution.** @btcxoomer, measured on their own three-node GB10
triangle; log excerpts reproduced with their permission.

**Related.**
[Trap 134](../evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md)
(link state is not path proof; this entry is the collective-transport mirror:
*device selection* is not path proof either),
[Trap 114](114-hardcoded-rdma-gid-index-is-not-portable.md) (GID index
portability; ruled out here before the real cause was found),
[U20](../../upstream/U20-gb10-direct-qsfp-single-hca-half-bandwidth.md)
(same GB10 dual-rail hardware, the bandwidth half rather than the routing half).
